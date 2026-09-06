/**
 * Transforme tout <select class="searchable-select"> en champ filtrable au clavier.
 * Le <select> d'origine reste dans le DOM (masqué) et continue de porter la valeur
 * soumise avec le formulaire : aucune dépendance externe, aucun changement côté serveur.
 */
(function () {
    function texteOption(option) {
        return option.textContent.trim();
    }

    function enhance(select) {
        if (select.dataset.searchEnhanced) return;
        select.dataset.searchEnhanced = 'true';

        var wrapper = document.createElement('div');
        wrapper.className = 'searchable-select-wrapper';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        var input = document.createElement('input');
        input.type = 'text';
        input.className = (select.className
            .replace(/\bform-select\b/, 'form-control')
            .replace(/\bsearchable-select\b/, '')
            .trim() + ' searchable-select-input').trim();
        input.autocomplete = 'off';
        input.placeholder = select.dataset.placeholder || 'Rechercher...';

        // Le label existant cible l'id du select : on le transfère à l'input visible.
        if (select.id) {
            input.id = select.id;
            select.removeAttribute('id');
        }

        var dropdown = document.createElement('div');
        dropdown.className = 'searchable-select-dropdown';

        wrapper.appendChild(input);
        wrapper.appendChild(dropdown);
        select.classList.add('searchable-select-native');

        var toutesOptions = Array.prototype.slice.call(select.options)
            .map(function (o) { return { value: o.value, text: texteOption(o) }; });
        var optionVide = toutesOptions.find(function (o) { return !o.value; });
        var options = toutesOptions.filter(function (o) { return o.value; });

        function texteSelection() {
            var opt = select.options[select.selectedIndex];
            return (opt && opt.value) ? texteOption(opt) : '';
        }

        function syncInputAvecSelect() {
            input.value = texteSelection();
        }
        syncInputAvecSelect();

        function fermerDropdown() {
            dropdown.classList.remove('show');
            syncInputAvecSelect();
        }

        function choisir(option) {
            select.value = option.value;
            input.value = option.text;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            fermerDropdown();
        }

        function creerItem(o, premier) {
            var item = document.createElement('div');
            item.className = 'searchable-select-item';
            if (o.value === select.value) item.classList.add('active');
            if (premier) item.classList.add('hover');
            item.textContent = o.text || 'Aucun véhicule';
            item.dataset.value = o.value;
            item.addEventListener('mousedown', function (e) {
                e.preventDefault();
                choisir(o);
            });
            return item;
        }

        function afficherListe(filtre) {
            var terme = filtre.trim().toLowerCase();
            var matches = options.filter(function (o) {
                return !terme || o.text.toLowerCase().indexOf(terme) !== -1;
            });
            dropdown.innerHTML = '';

            // L'option vide ("aucun véhicule") n'est proposée que hors recherche active,
            // pour pouvoir désassigner le véhicule sans devoir taper quoi que ce soit.
            var afficheOptionVide = !!optionVide && !terme;
            if (afficheOptionVide) {
                dropdown.appendChild(creerItem(optionVide, matches.length === 0));
            }

            matches.forEach(function (o, idx) {
                dropdown.appendChild(creerItem(o, idx === 0 && !afficheOptionVide));
            });

            if (!afficheOptionVide && matches.length === 0) {
                var vide = document.createElement('div');
                vide.className = 'searchable-select-empty';
                vide.textContent = 'Aucun résultat';
                dropdown.appendChild(vide);
            }
        }

        function ouvrirDropdown() {
            afficherListe('');
            dropdown.classList.add('show');
        }

        input.addEventListener('focus', function () {
            input.select();
            ouvrirDropdown();
        });
        input.addEventListener('input', function () {
            afficherListe(input.value);
            dropdown.classList.add('show');
        });
        input.addEventListener('blur', function () {
            // Laisse le temps au mousedown de la liste de s'exécuter avant fermeture.
            setTimeout(fermerDropdown, 150);
        });
        input.addEventListener('keydown', function (e) {
            var items = Array.prototype.slice.call(dropdown.querySelectorAll('.searchable-select-item'));
            var idx = items.findIndex(function (i) { return i.classList.contains('hover'); });

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (idx >= 0) items[idx].classList.remove('hover');
                idx = (idx + 1) % items.length;
                if (items[idx]) { items[idx].classList.add('hover'); if (items[idx].scrollIntoView) items[idx].scrollIntoView({ block: 'nearest' }); }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (idx >= 0) items[idx].classList.remove('hover');
                idx = (idx - 1 + items.length) % items.length;
                if (items[idx]) { items[idx].classList.add('hover'); if (items[idx].scrollIntoView) items[idx].scrollIntoView({ block: 'nearest' }); }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                var cible = items[idx] || items[0];
                if (cible) {
                    var toutes = optionVide ? [optionVide].concat(options) : options;
                    var opt = toutes.find(function (o) { return o.value === cible.dataset.value; });
                    if (opt) choisir(opt);
                }
            } else if (e.key === 'Escape') {
                fermerDropdown();
                input.blur();
            }
        });

        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) {
                dropdown.classList.remove('show');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('select.searchable-select').forEach(enhance);
    });
})();
