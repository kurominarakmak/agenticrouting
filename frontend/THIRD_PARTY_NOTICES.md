# Third party notices

`src/vendor/Button.tsx` and `Button.module.css` are copied unchanged from DeepSeek Harness, commit `39163dd30f703a79079e2d2446545cff3c453738`, `packages/client/ui-primitives/src/`. Copyright (c) 2026 DeepSeek, MIT. The complete license is retained in `src/vendor/DSH-LICENSE`.

Upstream: https://github.com/deepseek-ai/deepseek-harness

Syntropic supplies the surrounding tokens and layout. This is a small pinned source reuse, not a fork of the DSH core or a claim of a stable DSH package interface. Review the two files and their license when updating.

React, Vite, react-markdown, remark-gfm, remark-math, rehype-katex, rehype-highlight and their transitive dependencies retain their package licenses in the installed dependencies. Inter and JetBrains Mono licenses remain under `assets/`.

The optional backend runtime uses the officially distributed `deepseek-harness-sdk==0.2.2rc2` and its bundled runtime dependency under their package licenses. The Syntropic adapter does not fork or vendor the DSH agent core.
