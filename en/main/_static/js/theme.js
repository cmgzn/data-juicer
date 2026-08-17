/**
 * Data-Juicer Sphinx Theme - JavaScript
 */

(function() {
  'use strict';

  // ==================== Dark Mode ====================
  function syncPygmentsDark(theme) {
    var link = document.getElementById('pygments-dark-css');
    if (link) link.disabled = (theme !== 'dark');
  }

  function initTheme() {
    const stored = localStorage.getItem('dj-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = stored || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    syncPygmentsDark(theme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('dj-theme', next);
    syncPygmentsDark(next);
  }

  // ==================== Sidebar ====================
  function initSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (!toggle || !sidebar) return;

    toggle.addEventListener('click', function() {
      sidebar.classList.toggle('open');
      overlay.classList.toggle('visible');
    });

    if (overlay) {
      overlay.addEventListener('click', function() {
        sidebar.classList.remove('open');
        overlay.classList.remove('visible');
      });
    }
  }

  // ==================== Dropdowns ====================
  function initDropdowns() {
    document.querySelectorAll('.dropdown').forEach(function(dropdown) {
      var trigger = dropdown.querySelector('.dropdown-trigger');
      if (!trigger) return;

      trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        var wasActive = dropdown.classList.contains('active');
        closeAllDropdowns();
        if (!wasActive) {
          dropdown.classList.add('active');
        }
      });
    });

    document.addEventListener('click', closeAllDropdowns);
  }

  function closeAllDropdowns() {
    document.querySelectorAll('.dropdown.active').forEach(function(d) {
      d.classList.remove('active');
    });
  }

  // ==================== Copy Buttons ====================
  function initCopyButtons() {
    document.querySelectorAll('.highlight pre, .article > pre').forEach(function(pre) {
      if (pre.querySelector('.copy-button')) return;

      var wrapper = pre.closest('.highlight') || pre;
      wrapper.style.position = 'relative';

      var btn = document.createElement('button');
      btn.className = 'copy-button';
      btn.setAttribute('aria-label', 'Copy code');
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M3 11V2.5A1.5 1.5 0 014.5 1H11"/></svg>';

      btn.addEventListener('click', function() {
        var code = pre.textContent || pre.innerText;
        navigator.clipboard.writeText(code).then(function() {
          btn.classList.add('copied');
          btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3.5 8.5 6.5 11.5 12.5 5.5"/></svg>';
          setTimeout(function() {
            btn.classList.remove('copied');
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M3 11V2.5A1.5 1.5 0 014.5 1H11"/></svg>';
          }, 2000);
        });
      });

      wrapper.appendChild(btn);
    });
  }

  // ==================== TOC Active Tracking ====================
  function initTocTracking() {
    var tocLinks = document.querySelectorAll('.toc-sidebar a');
    if (!tocLinks.length) return;

    var headings = [];
    tocLinks.forEach(function(link) {
      var id = link.getAttribute('href');
      if (id && id.startsWith('#')) {
        var heading = document.getElementById(id.slice(1));
        if (heading) headings.push({ el: heading, link: link });
      }
    });

    if (!headings.length) return;

    function updateActive() {
      var scrollTop = window.scrollY + 100;
      var active = headings[0];

      for (var i = 0; i < headings.length; i++) {
        if (headings[i].el.offsetTop <= scrollTop) {
          active = headings[i];
        }
      }

      tocLinks.forEach(function(l) { l.classList.remove('active'); });
      if (active) active.link.classList.add('active');
    }

    window.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
  }

  // ==================== Sidebar Active State ====================
  function initSidebarActive() {
    var current = window.location.pathname;
    document.querySelectorAll('.sidebar-nav a').forEach(function(link) {
      var href = link.getAttribute('href');
      if (href && (current.endsWith(href) || current.includes(href.replace('.html', '')))) {
        link.closest('li').classList.add('current');
        // Expand parent lists
        var parent = link.closest('li').parentElement;
        while (parent) {
          if (parent.tagName === 'UL' && parent.parentElement && parent.parentElement.tagName === 'LI') {
            parent.style.display = 'block';
          }
          parent = parent.parentElement;
        }
      }
    });
  }

  // ==================== Search Modal ====================
  function initSearch() {
    var trigger = document.getElementById('search-trigger');
    var overlay = document.getElementById('search-overlay');
    var input = document.getElementById('search-modal-input');

    if (!trigger || !overlay) return;

    function openSearch() {
      overlay.classList.add('visible');
      if (input) input.focus();
    }

    function closeSearch() {
      overlay.classList.remove('visible');
      if (input) input.value = '';
    }

    trigger.addEventListener('click', openSearch);

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) closeSearch();
    });

    document.addEventListener('keydown', function(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (overlay.classList.contains('visible')) {
          closeSearch();
        } else {
          openSearch();
        }
      }
      if (e.key === 'Escape' && overlay.classList.contains('visible')) {
        closeSearch();
      }
    });

    // Redirect to Sphinx search on Enter
    if (input) {
      input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && input.value.trim()) {
          var searchUrl = document.querySelector('link[rel="search"]');
          if (searchUrl) {
            window.location.href = searchUrl.href.replace('search.html', '') + 'search.html?q=' + encodeURIComponent(input.value);
          } else {
            window.location.href = 'search.html?q=' + encodeURIComponent(input.value);
          }
        }
      });
    }
  }

  // ==================== Version switcher ====================
  function initVersionSwitcher() {
    var dropdown = document.getElementById('version-dropdown');
    if (!dropdown) return;
    var url = dropdown.getAttribute('data-versions-url');
    if (!url) return;
    var prefix = dropdown.getAttribute('data-link-prefix') || '../';
    var page = dropdown.getAttribute('data-page') || 'index';
    var current = dropdown.getAttribute('data-current') || 'main';

    function render(versions) {
      var panel = dropdown.querySelector('.dropdown-panel');
      if (!panel || !versions || !versions.length) return;
      panel.innerHTML = versions.map(function(v) {
        var href = prefix + v + '/' + page + '.html';
        var cls = 'dropdown-item' + (v === current ? ' active' : '');
        return '<a href="' + href + '" class="' + cls + '">' + v + '</a>';
      }).join('');
    }

    var cached = null;
    try {
      cached = sessionStorage.getItem('dj-versions');
    } catch (e) { /* sessionStorage unavailable */ }
    if (cached) {
      try { render(JSON.parse(cached)); return; } catch (e) { /* refetch below */ }
    }

    fetch(url).then(function(resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    }).then(function(data) {
      if (data && Array.isArray(data.versions) && data.versions.length) {
        try { sessionStorage.setItem('dj-versions', JSON.stringify(data.versions)); } catch (e) {}
        render(data.versions);
      }
    }).catch(function() {
      // Keep the server-rendered fallback items on any failure
    });
  }

  // ==================== Init ====================
  initTheme();

  document.addEventListener('DOMContentLoaded', function() {
    var themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', toggleTheme);
    }

    initSidebar();
    initDropdowns();
    initVersionSwitcher();
    initCopyButtons();
    initTocTracking();
    initSidebarActive();
    initSearch();
  });
})();
