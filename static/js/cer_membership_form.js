/**
 * CER Hub - modulo di adesione a una CER (templates/core/cer_join.html)
 *
 * Mostra o nasconde le sezioni del modulo in base al "Tipo di Membro"
 * scelto (select #member_type_select):
 *   - .consumer-only  -> Consumatore e Prosumer
 *   - .producer-only  -> Produttore e Prosumer
 *   - .prosumer-only  -> solo Prosumer
 * I campi con classe .producer-field vengono resi visibili e obbligatori
 * solo quando servono; quando sono nascosti vengono disabilitati, cosi'
 * non sono inviati e non bloccano l'invio del modulo.
 *
 * Nessuna dipendenza esterna.
 */
(function () {
    'use strict';

    // Campi che il server richiede a Produttori e Prosumer
    var REQUIRED_PRODUCER_FIELDS = [
        'annual_production',
        'plant_power',
        'installation_date',
        'gaudi_document',
        'plant_authorization',
        'conformity_declaration',
        'gse_practice',
        'panels_photo',
        'inverter_photo'
    ];

    function setSectionVisible(section, visible) {
        section.style.display = visible ? 'block' : 'none';
    }

    function setFieldEnabled(field, enabled) {
        field.style.display = enabled ? '' : 'none';
        field.disabled = !enabled;
        if (REQUIRED_PRODUCER_FIELDS.indexOf(field.name) !== -1) {
            field.required = enabled;
        }
    }

    function init() {
        var select = document.getElementById('member_type_select') ||
            document.querySelector('select[name="member_type"]');
        if (!select) {
            return;
        }
        var form = select.form || document;

        function update() {
            var type = select.value;
            var isProducer = type === 'PRODUCER' || type === 'PROSUMER';
            var isConsumer = type === 'CONSUMER' || type === 'PROSUMER';

            form.querySelectorAll('.consumer-only').forEach(function (el) {
                setSectionVisible(el, isConsumer);
            });
            form.querySelectorAll('.producer-only').forEach(function (el) {
                setSectionVisible(el, isProducer);
            });
            form.querySelectorAll('.prosumer-only').forEach(function (el) {
                setSectionVisible(el, type === 'PROSUMER');
            });
            form.querySelectorAll('.producer-field').forEach(function (field) {
                setFieldEnabled(field, isProducer);
            });
        }

        select.addEventListener('change', update);
        update();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
