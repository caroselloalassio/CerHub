/**
 * CER Hub - codice POD e cabina primaria
 *
 * Questo script NON interroga alcun servizio esterno. Si limita a:
 *   - normalizzare e controllare il formato del codice POD
 *     (campi con attributo data-pod-input), es. IT001E12345678;
 *   - normalizzare e controllare il formato del codice della cabina
 *     primaria (campi con attributo data-substation-input), es. AC001E01027;
 *   - mostrare sotto il campo il collegamento alla mappa ufficiale del GSE,
 *     dove si puo' verificare a quale cabina primaria appartiene un indirizzo.
 *
 * Il controllo e' solo un aiuto alla compilazione: non blocca l'invio del
 * modulo (la validazione vera resta sul server).
 *
 * Nessuna dipendenza esterna.
 */
(function () {
    'use strict';

    var GSE_MAP_URL = 'https://www.gse.it/servizi-per-te/autoconsumo/mappa-interattiva-delle-cabine-primarie';

    // POD: IT + 3 cifre (distributore) + E + 8 cifre (+ eventuale cifra di controllo)
    var POD_PATTERN = /^IT\d{3}E\d{8,9}$/;
    // Cabina primaria (area convenzionale GSE): AC + 3 cifre + E + 5 cifre
    var SUBSTATION_PATTERN = /^AC\d{3}E\d{5}$/;

    function normalizeCode(value) {
        return String(value || '').toUpperCase().replace(/[\s.\-_]/g, '');
    }

    function isValidPod(value) {
        return POD_PATTERN.test(normalizeCode(value));
    }

    function isValidSubstationCode(value) {
        return SUBSTATION_PATTERN.test(normalizeCode(value));
    }

    function gseMapLink(text) {
        var link = document.createElement('a');
        link.href = GSE_MAP_URL;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = text;
        return link;
    }

    function addHint(input) {
        var hint = document.createElement('div');
        hint.className = 'form-text';
        input.insertAdjacentElement('afterend', hint);
        return hint;
    }

    function setMessage(hint, text, isError, withMapLink) {
        hint.textContent = text;
        hint.classList.toggle('text-danger', !!isError);
        if (withMapLink) {
            hint.appendChild(document.createTextNode(' '));
            hint.appendChild(gseMapLink('Apri la mappa GSE delle cabine primarie'));
        }
    }

    function setState(input, state) {
        input.classList.toggle('is-valid', state === 'valid');
        input.classList.toggle('is-invalid', state === 'invalid');
    }

    function initPodInput(input) {
        var hint = addHint(input);
        var defaultText = 'Trovi il codice POD in bolletta (es. IT001E12345678). ' +
            'Per sapere a quale cabina primaria appartiene la tua fornitura:';

        function check() {
            input.value = normalizeCode(input.value);
            if (!input.value) {
                setState(input, null);
                setMessage(hint, defaultText, false, true);
            } else if (isValidPod(input.value)) {
                setState(input, 'valid');
                setMessage(hint, 'Formato del codice POD corretto. Verifica la cabina primaria della tua fornitura:', false, true);
            } else {
                setState(input, 'invalid');
                setMessage(hint, 'Il codice POD non sembra corretto: deve avere la forma IT001E12345678 ' +
                    '(IT, 3 cifre, E, 8 o 9 cifre).', true, false);
            }
        }

        input.addEventListener('blur', check);
        input.addEventListener('change', check);
        check();
    }

    function initSubstationInput(input) {
        var hint = addHint(input);
        var defaultText = 'Codice della cabina primaria (es. AC001E01027).';

        function check() {
            var code = normalizeCode(input.value);
            if (!code) {
                setState(input, null);
                setMessage(hint, defaultText, false, true);
            } else if (isValidSubstationCode(code)) {
                input.value = code;
                setState(input, 'valid');
                setMessage(hint, 'Formato del codice cabina corretto.', false, true);
            } else {
                setState(input, 'invalid');
                setMessage(hint, 'Il codice non sembra quello di una cabina primaria: deve avere la forma ' +
                    'AC001E01027 (AC, 3 cifre, E, 5 cifre).', true, true);
            }
        }

        input.addEventListener('blur', check);
        input.addEventListener('change', check);
        check();
    }

    function init() {
        document.querySelectorAll('[data-pod-input]').forEach(initPodInput);
        document.querySelectorAll('[data-substation-input]').forEach(initSubstationInput);
    }

    // Funzioni riutilizzabili da altre pagine
    window.PrimarySubstationLookup = {
        GSE_MAP_URL: GSE_MAP_URL,
        normalizeCode: normalizeCode,
        isValidPod: isValidPod,
        isValidSubstationCode: isValidSubstationCode,
        init: init
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
