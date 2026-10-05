/*
 * CER Hub – consenso ai cookie (senza servizi esterni)
 *
 * - La scelta è salvata nel cookie "cerhub_consent" (valori: "analytics" | "none"),
 *   valido 6 mesi su tutto cerhub.it, così vale sia per il sito sia per l'area soci.
 * - Google Analytics non viene caricato finché l'utente non accetta.
 * - Chiudere il banner con la X equivale a rifiutare.
 * - Qualsiasi elemento con classe "js-cerhub-cookie-prefs" riapre il banner.
 *
 * Configurazione: window.CERHUB_CONSENT = { policyUrl: '...', gaId: 'G-XXXX' | null, gaConfig: {...} }
 * Gli script già presenti nella pagina con type="text/plain" data-cerhub-consent="analytics"
 * vengono attivati dopo il consenso.
 */
(function () {
    'use strict';

    var cfg = window.CERHUB_CONSENT || {};
    var COOKIE = 'cerhub_consent';
    var MAX_AGE = 60 * 60 * 24 * 180;
    var activated = false;

    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    if (typeof window.gtag !== 'function') { window.gtag = gtag; }

    function readChoice() {
        var m = document.cookie.match(/(?:^|;\s*)cerhub_consent=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : null;
    }

    function cookieDomain() {
        var h = location.hostname;
        return (h === 'cerhub.it' || /\.cerhub\.it$/.test(h)) ? '; domain=.cerhub.it' : '';
    }

    function saveChoice(value) {
        document.cookie = COOKIE + '=' + encodeURIComponent(value) + '; path=/; max-age=' + MAX_AGE +
            cookieDomain() + '; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');
    }

    function deleteCookie(name) {
        var domains = ['', '; domain=' + location.hostname, '; domain=.cerhub.it'];
        for (var i = 0; i < domains.length; i++) {
            document.cookie = name + '=; path=/; max-age=0' + domains[i];
        }
    }

    function removeAnalyticsCookies() {
        var parts = document.cookie.split(';');
        for (var i = 0; i < parts.length; i++) {
            var name = parts[i].split('=')[0].replace(/^\s+/, '');
            if (name === '_ga' || name.indexOf('_ga_') === 0 || name === '_gid' || name === '_gat') {
                deleteCookie(name);
            }
        }
    }

    function loadScript(src) {
        var s = document.createElement('script');
        s.async = true;
        s.src = src;
        document.head.appendChild(s);
    }

    function activateAnalytics() {
        if (activated) { return; }
        activated = true;
        window.gtag('consent', 'update', { analytics_storage: 'granted' });

        // script predisposti dalla pagina e tenuti fermi fino al consenso
        var blocked = document.querySelectorAll('script[type="text/plain"][data-cerhub-consent="analytics"]');
        for (var i = 0; i < blocked.length; i++) {
            var old = blocked[i];
            var src = old.getAttribute('src') || old.getAttribute('data-src');
            if (src) {
                loadScript(src);
            } else if (old.text) {
                var inline = document.createElement('script');
                inline.text = old.text;
                document.head.appendChild(inline);
            }
            old.setAttribute('data-cerhub-consent', 'activated');
        }

        if (cfg.gaId) {
            window.gtag('js', new Date());
            window.gtag('config', cfg.gaId, cfg.gaConfig || {});
            loadScript('https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(cfg.gaId));
            var queued = cfg.events || [];
            for (var j = 0; j < queued.length; j++) {
                window.gtag('event', queued[j].name, queued[j].params || {});
            }
        }
    }

    function hideBanner() {
        var el = document.getElementById('cerhub-consent');
        if (el) { el.parentNode.removeChild(el); }
    }

    function choose(value) {
        var previous = readChoice();
        saveChoice(value);
        hideBanner();
        if (value === 'analytics') {
            activateAnalytics();
        } else {
            window.gtag('consent', 'update', { analytics_storage: 'denied' });
            removeAnalyticsCookies();
            // se l'utente aveva accettato e ora rifiuta, serve ricaricare per fermare gli script già attivi
            if (previous === 'analytics' && activated) { location.reload(); }
        }
    }

    function showBanner() {
        if (document.getElementById('cerhub-consent')) { return; }
        var policy = cfg.policyUrl || '/cookie-policy/';
        var box = document.createElement('div');
        box.id = 'cerhub-consent';
        box.setAttribute('role', 'dialog');
        box.setAttribute('aria-live', 'polite');
        box.setAttribute('aria-label', 'Preferenze sui cookie');
        box.innerHTML =
            '<style>' +
            '#cerhub-consent{position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483000;max-width:760px;margin:0 auto;' +
            'background:#ffffff;color:#272727;border:1px solid #d9e2df;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.18);' +
            'padding:20px 48px 18px 22px;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}' +
            '#cerhub-consent p{margin:0 0 14px;color:#272727;font-size:15px;line-height:1.55}' +
            '#cerhub-consent a{color:#00796b;text-decoration:underline}' +
            '#cerhub-consent .cc-title{font-weight:700;margin-bottom:6px;font-size:16px}' +
            '#cerhub-consent .cc-actions{display:flex;flex-wrap:wrap;gap:10px}' +
            '#cerhub-consent button.cc-btn{flex:1 1 160px;cursor:pointer;border-radius:100em;padding:10px 18px;font:inherit;font-weight:700;' +
            'border:2px solid #00796b;background:#ffffff;color:#00796b;text-transform:none;letter-spacing:0;box-shadow:none;text-shadow:none}' +
            '#cerhub-consent button.cc-btn:hover,#cerhub-consent button.cc-btn:focus{background:#00796b;color:#ffffff}' +
            '#cerhub-consent button.cc-close{position:absolute;top:8px;right:10px;width:32px;height:32px;border:0;background:transparent;' +
            'color:#555555;font-size:24px;line-height:1;cursor:pointer;padding:0;box-shadow:none;text-shadow:none}' +
            '</style>' +
            '<button type="button" class="cc-close" aria-label="Chiudi e rifiuta i cookie non necessari">&times;</button>' +
            '<p class="cc-title">Cookie</p>' +
            '<p>Usiamo cookie tecnici, necessari al funzionamento, e, solo se acconsenti, cookie statistici di Google Analytics ' +
            'per capire come viene usato il sito. Puoi cambiare idea in ogni momento da &ldquo;Preferenze cookie&rdquo; a fondo pagina. ' +
            '<a href="' + policy + '">Leggi la cookie policy</a>.</p>' +
            '<div class="cc-actions">' +
            '<button type="button" class="cc-btn" data-cc="none">Rifiuta</button>' +
            '<button type="button" class="cc-btn" data-cc="analytics">Accetta</button>' +
            '</div>';
        document.body.appendChild(box);
        box.querySelector('.cc-close').addEventListener('click', function () { choose('none'); });
        var buttons = box.querySelectorAll('button[data-cc]');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].addEventListener('click', function () { choose(this.getAttribute('data-cc')); });
        }
    }

    function init() {
        var choice = readChoice();
        if (choice === 'analytics') {
            activateAnalytics();
        } else if (choice !== 'none') {
            showBanner();
        }
        document.addEventListener('click', function (ev) {
            var t = ev.target;
            while (t && t !== document) {
                if (t.className && typeof t.className === 'string' && t.className.indexOf('js-cerhub-cookie-prefs') !== -1) {
                    ev.preventDefault();
                    showBanner();
                    return;
                }
                t = t.parentNode;
            }
        });
    }

    window.cerhubConsent = { open: showBanner, choice: readChoice };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
