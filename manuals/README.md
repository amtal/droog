PDFs (lower case .pdf extension) go in sub-folders like these.


They can also go into `../../{bv.arch.name}/**/*.pdf`, with some guessing of endianness-agnostic plugin names. (This only matters if you have a custom architecture plugin.)

Anything that looks like a width (64,32) or an endianness (_le, _be, el, eb, be, etc) gets stripped out, so these don't exactly match Binary Ninja arch names. As a result aarch64 (formerly known as arm64, aarm, and whatever else) is just aarch.  Oh well.

Restart Binary Ninja if you change PDFs around.
