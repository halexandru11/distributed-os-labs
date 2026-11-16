#!/usr/bin/env python3
"""Export the Markdown report and its SVG charts to one offline HTML file.

Requires markdown-it-py. Run: python3 export_report.py results/study/report.md
"""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from markdown_it import MarkdownIt

SVG = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', SVG[1:-1])
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def mark_heatmap_minima(root, name, summary):
    """Use measured values, not raster colors, to choose column winners."""
    from benchmark import SHAPES, SCHEDULES, VARIANTS

    campaign = 'dimensions' if name == 'dimensions' else 'schedules'
    variants = VARIANTS if name == 'dimensions' else VARIANTS[1:]
    columns = SHAPES if name == 'dimensions' else SCHEDULES
    machines = sorted({row['machine'] for row in summary})
    axes = [a for a in root.iter(SVG + 'g')
            if a.get('id', '').startswith('axes_')]
    for axis, machine in zip(axes, machines):
        image_group = next((g for g in axis if g.find(SVG + 'image') is not None), None)
        if image_group is None:
            continue
        clip_id = image_group.get('clip-path')[5:-1]
        clip = next(c for c in root.iter(SVG + 'clipPath') if c.get('id') == clip_id)
        rect = clip.find(SVG + 'rect')
        x, y, width, height = (float(rect.get(k)) for k in ('x', 'y', 'width', 'height'))
        cw, ch = width / len(columns), height / len(variants)
        for column_index, column in enumerate(columns):
            candidates = {}
            entries = {}
            for row in summary:
                if (row['machine'] != machine or row['campaign'] != campaign
                        or row['dataset'] != 'random'
                        or row['variant'] not in variants):
                    continue
                key = tuple(int(row[k]) for k in ('n', 'm', 'r'))
                if name == 'schedules':
                    chunk = int(row['chunk_i'])
                    key = row['schedule_i'] + (f':{chunk}' if chunk else '')
                if key == column:
                    entries[row['variant']] = row
                    if row['status'] == 'OK' and math.isfinite(float(row['mean_seconds'])):
                        candidates[row['variant']] = float(row['mean_seconds'])
            for row_index, variant in enumerate(variants):
                entry = entries.get(variant)
                value = f"{float(entry['mean_seconds']) * 1000:.8g} ms" if variant in candidates else (entry['status'] if entry else 'Date indisponibile')
                column_label = '×'.join(map(str, column)) if isinstance(column, tuple) else column
                ET.SubElement(axis, SVG + 'rect', {
                    'x': str(x + column_index * cw), 'y': str(y + row_index * ch),
                    'width': str(cw), 'height': str(ch), 'fill': 'transparent',
                    'data-tooltip': f'{machine} · {variant} · {column_label}\n{value}',
                    'tabindex': '0', 'class': 'heatmap-cell'})
            if not candidates:
                continue
            best = min(candidates.values())
            for variant, value in candidates.items():
                if value != best:
                    continue
                outline = ET.SubElement(axis, SVG + 'rect', {
                    'x': str(x + column_index * cw + 1.5),
                    'y': str(y + variants.index(variant) * ch + 1.5),
                    'width': str(cw - 3), 'height': str(ch - 3),
                    'fill': 'none', 'stroke': '#e00000', 'stroke-width': '2.5',
                    'vector-effect': 'non-scaling-stroke', 'class': 'column-best',
                    'pointer-events': 'none',
                    'data-machine': machine, 'data-column': str(column_index),
                    'data-variant': variant})
                ET.SubElement(outline, SVG + 'title').text = f'{variant}: {value * 1000:.6g} ms, minimum în coloană'


def interactive_svg(path, prefix, label, summary=()):
    root = ET.fromstring(path.read_text(), parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True)))
    root.set('role', 'img')
    root.set('aria-label', label)
    # Matplotlib scopes this rule to SVG when exporting; keep it local in HTML.
    for style in root.iter(SVG + 'style'):
        style.text = (style.text or '').replace('*{', '.chart svg *{')

    def color(node):
        for element in node.iter():
            match = re.search(r'fill: (#[0-9a-fA-F]{6})', element.get('style', ''))
            if match:
                return match[1].lower()
        return None

    description = root.find('.//{http://purl.org/dc/elements/1.1/}description')
    tooltip_data = json.loads(description.text) if description is not None else {}

    def mark(node, key):
        node.set('data-series', key)
        node.set('tabindex', '0')
        node.set('aria-label', key)
        node.set('class', 'series')
        data = tooltip_data.get(node.get('id'))
        if data and data['kind'] == 'bar' and math.isfinite(data['value']):
            node.set('data-tooltip', f"{key} · {data['category']}\n{data['value']:.8g} {data['unit']}")
        elif data and data['kind'] == 'line':
            markers = [n for n in node.iter(SVG + 'use') if n.get('x') is not None and n.get('y') is not None]
            points = []
            for marker, (x, y) in zip(markers, data['points']):
                if math.isfinite(x) and math.isfinite(y):
                    points.append({'x': float(marker.get('x')), 'y': float(marker.get('y')),
                                   'text': f"{key} · GP={x:g}\n{y:.8g} {data['unit']}"})
            if points:
                node.set('data-points', json.dumps(points))
            elif data['points']:
                x, y = data['points'][0]
                value = x if key == 'logical CPUs' else y
                suffix = ' CPU logice' if key == 'logical CPUs' else f" {data['unit']}"
                node.set('data-tooltip', f'{key}\n{value:.8g}{suffix}')

    for axis in root.iter(SVG + 'g'):
        if not axis.get('id', '').startswith('axes_'):
            continue
        lines = [n for n in axis if n.get('id', '').startswith('line2d_')]
        bars = [n for n in axis if n.get('id', '').startswith('patch_')
                and color(n) not in (None, '#ffffff', '#000000')]
        handles = []
        for legend in axis:
            if not legend.get('id', '').startswith('legend_'):
                continue
            handle = None
            for entry in legend:
                entry_id = entry.get('id', '')
                if entry_id.startswith(('line2d_', 'patch_')):
                    handle = entry
                elif entry_id.startswith('text_') and handle is not None:
                    # Matplotlib preserves the original label in an SVG comment.
                    label = ''.join(n.text or '' for n in entry.iter()
                                    if n.tag is ET.Comment).strip()
                    if not label:
                        label = ''.join(entry.itertext()).strip()
                    mark(handle, label)
                    mark(entry, label)
                    handles.append((handle, label))
                    handle = None
        line_handles = [(h, label) for h, label in handles
                        if h.get('id', '').startswith('line2d_')]
        for index, line in enumerate(lines):
            label = line_handles[index][1] if index < len(line_handles) else f'line-{index}'
            mark(line, label)
            if label == 'logical CPUs':
                line.set('pointer-events', 'none')
                line.attrib.pop('tabindex', None)
                line.attrib.pop('data-tooltip', None)
                line.attrib.pop('data-points', None)
                continue
            # A transparent stroke expands the target without changing the plot.
            for segment in list(line):
                if segment.tag == SVG + 'path' and 'd' in segment.attrib:
                    hit = ET.Element(SVG + 'path', {
                        'd': segment.get('d'), 'class': 'line-hit',
                        'fill': 'none', 'stroke': 'transparent',
                        'stroke-width': '16', 'pointer-events': 'stroke',
                        'vector-effect': 'non-scaling-stroke'})
                    if segment.get('transform'):
                        hit.set('transform', segment.get('transform'))
                    line.append(hit)
        bar_labels = {color(h): label for h, label in handles
                      if h.get('id', '').startswith('patch_')}
        for bar in bars:
            mark(bar, bar_labels.get(color(bar), color(bar)))
    if path.stem in ('dimensions', 'schedules') and summary:
        mark_heatmap_minima(root, path.stem, summary)
    # Each embedded chart needs independent clip paths, glyphs, and markers.
    ids = {node.get('id') for node in root.iter() if node.get('id')}
    for node in root.iter():
        for attr, value in list(node.attrib.items()):
            if attr == 'id':
                node.set(attr, prefix + value)
            else:
                value = re.sub(r'url\(#([^)]*)\)', lambda m: 'url(#' + prefix + m[1] + ')', value)
                if value.startswith('#') and value[1:] in ids:
                    value = '#' + prefix + value[1:]
                node.set(attr, value)
    return ET.tostring(root, encoding='unicode')


def export_report(source):
    md = MarkdownIt('commonmark', {'html': True}).enable('table')
    md.renderer.rules['table_open'] = lambda tokens, idx, options, env: (
        '<div class="table-scroll" tabindex="0" role="region" aria-label="Tabel cu rezultate"><table>\n')
    md.renderer.rules['table_close'] = lambda tokens, idx, options, env: '</table></div>\n'
    counter = 0
    with source.with_name('summary.csv').open(newline='') as stream:
        summary = list(csv.DictReader(stream))

    def image(tokens, idx, options, env):
        nonlocal counter
        token = tokens[idx]
        path = source.parent / token.attrGet('src')
        svg = path.with_suffix('.svg')
        if not svg.is_file():
            raise FileNotFoundError(f'Missing SVG chart: {svg}')
        counter += 1
        if svg.stem in ('dimensions', 'schedules'):
            note = '<span class="chart-note">Chenar roșu: cel mai mic timp valid din fiecare coloană. Egalitățile sunt marcate împreună.</span>'
        elif svg.stem == 'allocation':
            note = '<span class="directions"><span><b>↓</b> Timp mai mic = mai bine, în ambele grafice.</span></span>'
        else:
            up = svg.stem == 'speedup'
            arrow = '↑' if up else '↓'
            metric = 'Accelerare mai mare = mai bine' if up else 'Timp mai mic = mai bine'
            note = '<span class="directions">' + ''.join(
                f'<span>{html.escape(machine)} · <b>{arrow}</b> {metric}</span>'
                for machine in sorted({r['machine'] for r in summary})) + '</span>'
        return '<span class="chart">' + note + interactive_svg(svg, f'chart{counter}-', token.content, summary) + '</span>' 

    md.renderer.rules['image'] = image
    body = md.render(source.read_text())
    document = '''<!doctype html>
<html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HW2 | Rezultate experimentale măsurate</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#202b38;font:16px/1.65 system-ui,sans-serif}
main{max-width:1200px;margin:32px auto;padding:32px 40px;background:white;border-radius:12px}
h1,h2{line-height:1.25;color:#102d49}h1{font-size:2rem}h2{margin-top:2.4rem;font-size:1.4rem}
a{color:#1261a0}code{background:#edf1f5;padding:2px 5px;border-radius:4px;font-size:.88em}
.table-scroll{overflow:auto;max-height:70vh;margin:24px 0;border:1px solid #dbe2e8;border-radius:6px}table{border-collapse:separate;border-spacing:0;font-size:.85rem;width:100%}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dbe2e8}th{position:sticky;top:0;z-index:2;background:#edf2f7;box-shadow:0 1px 0 #b8c5d2}tr:nth-child(even){background:#f8fafc}
.chart{display:block;overflow-x:auto;margin:28px 0}.chart svg{display:block;width:100%;height:auto;min-width:650px}
.directions{display:flex;gap:16px;margin-bottom:8px}.directions>span{flex:1;background:#edf4fb;padding:8px 12px;border-radius:6px;font-size:13px}.directions b{font-size:22px;color:#126444}.chart-note{display:block;font-size:13px;color:#a00000;margin-bottom:8px}
.series{transition:opacity .12s;cursor:pointer}.series.dimmed{opacity:.15}.series:focus{outline:none;filter:drop-shadow(0 0 2px #527a9e)}
.tooltip{position:fixed;z-index:1000;pointer-events:none;white-space:pre-line;background:#142b42;color:white;padding:9px 12px;border-radius:6px;font-size:13px;box-shadow:0 3px 14px #0003;max-width:360px}.tooltip[hidden]{display:none}
details{margin:24px 0;border:1px solid #dbe2e8;border-radius:8px;padding:12px 16px}summary{cursor:pointer;font-weight:600;color:#1261a0}details[open] summary{margin-bottom:16px}
.hint{padding:12px 16px;background:#edf4fb;border-left:3px solid #3275af;font-size:.9rem}
@media(max-width:700px){main{margin:0;padding:20px;border-radius:0}h1{font-size:1.6rem}}
@media print{body{background:white}main{margin:0;padding:0}.series.dimmed{opacity:1}.table-scroll{max-height:none;overflow:visible;border:0}th{position:static;box-shadow:none}.chart svg{min-width:0}.hint{display:none}}
</style></head><body><main>

''' + body + '''</main><div class="tooltip" role="tooltip" hidden></div><script>
const tooltip = document.querySelector('.tooltip');
const hideTooltip = () => { tooltip.hidden = true; };
function showTooltip(item, event) {
  let text = item.dataset.tooltip;
  if (item.dataset.points) {
    const points = JSON.parse(item.dataset.points);
    const matrix = item.getScreenCTM();
    let nearest, distance = Infinity;
    for (const point of points) {
      const screen = new DOMPoint(point.x, point.y).matrixTransform(matrix);
      const d = (screen.x - event.clientX) ** 2 + (screen.y - event.clientY) ** 2;
      if (d < distance) { nearest = point; distance = d; }
    }
    text = nearest?.text;
  }
  if (!text) return hideTooltip();
  tooltip.textContent = text;
  tooltip.hidden = false;
  tooltip.style.left = Math.max(8, Math.min(event.clientX + 14, innerWidth - tooltip.offsetWidth - 8)) + 'px';
  tooltip.style.top = Math.max(8, Math.min(event.clientY + 14, innerHeight - tooltip.offsetHeight - 8)) + 'px';
}
for (const item of document.querySelectorAll('[data-tooltip], [data-points]')) {
  item.addEventListener('pointerenter', event => showTooltip(item, event));
  item.addEventListener('pointermove', event => showTooltip(item, event));
  item.addEventListener('pointerleave', hideTooltip);
  item.addEventListener('focus', () => {
    const box = item.getBoundingClientRect();
    showTooltip(item, {clientX: box.x + box.width / 2, clientY: box.y + box.height / 2});
  });
  item.addEventListener('blur', hideTooltip);
}
addEventListener('scroll', hideTooltip, true);
for (const chart of document.querySelectorAll('.chart')) {
  const series = [...chart.querySelectorAll('[data-series]')];
  const highlight = key => series.forEach(item => item.classList.toggle('dimmed', Boolean(key) && item.dataset.series !== key));
  for (const item of series) {
    item.addEventListener('pointerenter', () => highlight(item.dataset.series));
    item.addEventListener('pointerleave', () => highlight(null));
    item.addEventListener('focus', () => highlight(item.dataset.series));
    item.addEventListener('blur', () => highlight(null));
  }
}
</script></body></html>'''
    target = source.with_suffix('.html')
    target.write_text(document)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?', default=Path('results/study/report.md'))
    print(export_report(parser.parse_args().source))
