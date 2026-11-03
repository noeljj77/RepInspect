// Runs before the page paints, so a saved light theme never flashes dark first.
// Kept as a separate file because the production content security policy allows no inline scripts.
try {
  if (localStorage.getItem('repinspect-theme') === 'light') document.documentElement.dataset.theme = 'light'
} catch (error) {
  // Storage can be blocked; the default (dark) is fine.
}
