/**
 * Filtrage en direct générique pour les formulaires de recherche/liste
 * ("recherche automatique" — pas de clic sur un bouton "Rechercher").
 *
 * Usage sur un <form method="get"> :
 *   - data-live-filter="{% url '...:..._ajax' %}"  (obligatoire : endpoint AJAX)
 *   - data-target="idDuConteneurResultats"          (obligatoire : conteneur à remplacer)
 *   - data-count-target="idDuBadgeTotal"             (optionnel : badge total mis à jour via X-Nb-Total)
 *
 * Champs texte : filtrent avec un debounce (frappe). Selects et <input type="date"> :
 * filtrent immédiatement au changement. Liens "pills" (class="js-filter-pill"
 * data-name="..." data-value="...") : interceptés au clic ; sans JS, ce sont
 * des liens classiques qui continuent de fonctionner en navigation normale.
 */
(function () {
    function debounce(fn, delay) {
        let timer;
        return function () {
            clearTimeout(timer);
            const args = arguments;
            const context = this;
            timer = setTimeout(function () { fn.apply(context, args); }, delay);
        };
    }

    function initLiveFilter(form) {
        const ajaxUrl = form.dataset.liveFilter;
        const target = document.getElementById(form.dataset.target || '');
        if (!ajaxUrl || !target) return;

        const countBadge = form.dataset.countTarget ? document.getElementById(form.dataset.countTarget) : null;

        // État courant des groupes de "pills" (name -> value actif), initialisé
        // depuis le rendu serveur (classe "active" déjà posée côté template).
        const pillState = {};
        form.querySelectorAll('.js-filter-pill').forEach(function (pill) {
            if (pill.classList.contains('active')) {
                pillState[pill.dataset.name] = pill.dataset.value;
            }
        });

        function buildParams() {
            const params = new URLSearchParams();
            form.querySelectorAll('input[name], select[name]').forEach(function (field) {
                if (field.type === 'submit' || field.type === 'button') return;
                params.set(field.name, field.value);
            });
            Object.keys(pillState).forEach(function (name) {
                params.set(name, pillState[name]);
            });
            return params;
        }

        function rechercher() {
            target.style.opacity = '0.55';
            const params = buildParams();
            fetch(ajaxUrl + '?' + params.toString())
                .then(function (r) {
                    if (countBadge && r.headers.has('X-Nb-Total')) {
                        countBadge.textContent = r.headers.get('X-Nb-Total');
                    }
                    return r.text();
                })
                .then(function (html) {
                    target.innerHTML = html;
                    window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
                })
                .catch(function () {})
                .finally(function () { target.style.opacity = '1'; });
        }

        const rechercherDebounced = debounce(rechercher, 350);

        form.querySelectorAll('input[type="text"], input[type="search"], input[type="tel"]').forEach(function (input) {
            input.addEventListener('input', rechercherDebounced);
        });
        form.querySelectorAll('select, input[type="date"]').forEach(function (input) {
            input.addEventListener('change', rechercher);
        });
        form.querySelectorAll('.js-filter-pill').forEach(function (pill) {
            pill.addEventListener('click', function (e) {
                e.preventDefault();
                const name = this.dataset.name;
                form.querySelectorAll('.js-filter-pill[data-name="' + name + '"]').forEach(function (p) {
                    p.classList.remove('active');
                });
                this.classList.add('active');
                pillState[name] = this.dataset.value;
                rechercher();
            });
        });
        // Entrée clavier / clic sur le bouton restent utilisables (repli sans surprise).
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            rechercher();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-live-filter]').forEach(initLiveFilter);
    });
})();
