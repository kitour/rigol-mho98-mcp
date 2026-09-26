# Distribution contents

The software retains the upstream MIT license and copyright notice in `LICENSE`.
The MHO98 command index contains protocol syntax, argument types, static ranges
and corrections used by the executor. It does not contain manual prose, examples,
extracted Markdown or chapter context. Unknown or state-dependent ranges are
marked `dynamic`; the instrument still enforces its own operating limits.

Vendor PDFs and their converted references are local development inputs outside
this repository. Do not add them to source distributions or release assets.
For vendor documentation, use the RIGOL product download page:
https://www.rigol.com/intl/products/oscilloscope/MHO900.html

The two images under `media/mho98-probe-comp-*.png` are captures from the connected
instrument. They replaced the upstream demonstration images.

The September 2026 cleanup removed 58 converted reference files and the old
specification summary, and reduced all 654 index entries to execution data.
The command IDs and syntax were preserved. Catalog/executor checks ran offline;
no instrument commands were issued for this cleanup.
