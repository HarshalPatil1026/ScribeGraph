// Frontend configuration.
//
// R2_PUBLIC_URL: public URL of your Cloudflare R2 bucket (for example
// "https://pub-xxxxxxxx.r2.dev") when the pipeline uses R2 storage.
// Leave it empty to read articles from this website's own blogs/ folder
// (local storage mode, which is what GitHub Pages serves).
//
// The "Deploy site" GitHub Actions workflow overwrites this file when the
// R2_PUBLIC_URL repository variable is set, so you never need to commit a bucket URL.
window.CONFIG = {
    R2_PUBLIC_URL: ""
};
