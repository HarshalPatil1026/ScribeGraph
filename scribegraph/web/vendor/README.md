# Vendored front-end libraries

These files are copied unmodified from npm so the site has no third-party script
CDNs (faster, private, and it works offline). Each file keeps its license header.

| File | Package | Version | License |
|---|---|---|---|
| `marked.umd.js` | [marked](https://github.com/markedjs/marked) (`lib/marked.umd.js`) | 18.2.1 | MIT |
| `purify.min.js` | [DOMPurify](https://github.com/cure53/DOMPurify) (`dist/purify.min.js`) | 3.4.18 | MPL-2.0 OR Apache-2.0 |
| `highlight.min.js` | [@highlightjs/cdn-assets](https://github.com/highlightjs/highlight.js) | 11.12.0 | BSD-3-Clause |
| `github-dark.min.css` | @highlightjs/cdn-assets (`styles/github-dark.min.css`) | 11.12.0 | BSD-3-Clause |

To upgrade one, run for example `npm pack dompurify@latest`, extract it, and copy the
same file over the old one.
