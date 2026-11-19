# OpenMP Matrix Lab

Open [interactive.html](interactive.html) directly in a modern browser. Everything
needed is embedded in that file: styles, JavaScript, and the C snippets displayed
in the visualization. No installation, compilation, or server is required.

The lab simulates 13 matrix multiplication strategies, including sequential,
parallel, collapsed, and nested loops. You can edit matrices, configure threads
and scheduling, step through contributions, demonstrate data races, and save or
load a setup as JSON.

The displayed C snippets and line numbers are embedded snapshots from the original
`matmul.c`. Playback runs the JavaScript teaching model; wave counts represent
simulated work steps rather than measured performance.
