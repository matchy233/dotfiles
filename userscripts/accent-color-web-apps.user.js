// ==UserScript==
// @name         Windows Accent Color for Chrome Web Apps
// @version      1.2
// @match        http://*/*
// @match        https://*/*
// @run-at       document-end
// @noframes
// @grant        none
// @downloadURL  https://raw.githubusercontent.com/matchy233/dotfiles/main/userscripts/accent-color-web-apps.user.js
// @updateURL    https://raw.githubusercontent.com/matchy233/dotfiles/main/userscripts/accent-color-web-apps.user.js
// ==/UserScript==

(() => {
  const appModes = ['standalone', 'minimal-ui', 'window-controls-overlay', 'tabbed'];
  if (!appModes.some(mode => matchMedia(`(display-mode: ${mode})`).matches)) {
    return;
  }

  const theme = document.createElement('meta');
  theme.name = 'theme-color';
  theme.content = '#A67DF2';
  document.head.prepend(theme);
})();
