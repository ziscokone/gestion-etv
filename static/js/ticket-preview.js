/**
 * Aperçu de ticket pour la page de configuration de la compagnie.
 *
 * Fichier indépendant des fonctions d'impression réelles (guichet/vente.html,
 * voyages/voyage_detail.html) : il ne partage aucun code avec elles pour ne
 * prendre aucun risque sur le flux de vente en production. Il sert uniquement
 * à visualiser, avec des données factices, l'effet des réglages "Imprimer
 * avec souche" et "Message bas de ticket" avant même d'enregistrer.
 */
(function () {
    function billetDemo(utiliserSouche, messageBasTicket, compagnieNom, compagnieLogo) {
        return {
            numero: 'DEMO000000',
            numero_depart: '1',
            client_nom: 'Client Démo',
            numero_siege: 12,
            ligne: 'Abidjan → Korhogo',
            destination: 'Korhogo',
            date_depart: new Date().toLocaleDateString('fr-FR'),
            heure_depart: '07:30',
            montant: 7500,
            moyen_paiement_display: 'Cash',
            statut: 'paye',
            compagnie_nom: compagnieNom || 'COMPAGNIE DE TRANSPORT',
            compagnie_logo: compagnieLogo || '',
            gare_telephone: '01 23 45 67 89',
            gare_adresse: 'Gare routière — Adresse de démonstration',
            utiliser_souche: utiliserSouche,
            message_bas_ticket: messageBasTicket || '',
        };
    }

    function rendreTicketHTML(billet) {
        let html = `
        <div class="ticket-preview mb-3">
            <div class="ticket-header-row">
                <div class="ticket-logo">
                    ${billet.compagnie_logo
                        ? `<img src="${billet.compagnie_logo}" alt="Logo" class="ticket-logo-img">`
                        : `<div class="ticket-logo-placeholder"><i class="bi bi-bus-front"></i></div>`
                    }
                </div>
                <div class="ticket-gare-info">
                    <strong class="ticket-compagnie-nom">${billet.compagnie_nom}</strong>
                    ${billet.gare_telephone ? `<div class="ticket-gare-tel">Tel: ${billet.gare_telephone}</div>` : ''}
                    ${billet.gare_adresse ? `<div class="ticket-gare-adresse">${billet.gare_adresse}</div>` : ''}
                </div>
            </div>
            <div class="ticket-body">
                <div class="ticket-row"><span>N° Ticket:</span><strong>${billet.numero}</strong></div>
                <div class="ticket-row"><span>N° Depart:</span><strong>${billet.numero_depart}</strong></div>
                <div class="ticket-row"><span>Client:</span><span>${billet.client_nom}</span></div>
                <div class="ticket-row"><span>Siege:</span><strong class="ticket-siege">${billet.numero_siege}</strong></div>
                <hr>
                <div class="ticket-row"><span>Ligne:</span><span>${billet.ligne}</span></div>
                <div class="ticket-row"><span>Destination:</span><strong>${billet.destination}</strong></div>
                <div class="ticket-row"><span>Date:</span><span>${billet.date_depart}</span></div>
                <div class="ticket-row"><span>Heure:</span><span>${billet.heure_depart}</span></div>
                <hr>
                <div class="ticket-row ticket-montant">
                    <span>Montant:</span>
                    <strong>${Number(billet.montant).toLocaleString('fr-FR')} FCFA</strong>
                </div>
                <div class="ticket-row"><span>Paiement:</span><strong>${billet.moyen_paiement_display}</strong></div>
            </div>
        `;

        const msgHtml = billet.message_bas_ticket
            ? `<div class="ticket-message-bas">${billet.message_bas_ticket}</div>`
            : '';

        if (billet.utiliser_souche) {
            if (msgHtml) html += msgHtml;
            html += `
            <div class="ticket-separator-cut">✂ - - - - - - - - - - - - - - - - - - - - - - ✂</div>
            <div class="ticket-souche">
                <div class="souche-watermark">SOUCHE</div>
                <div class="souche-header">SOUCHE</div>
                <div class="ticket-row"><span>N° Depart:</span><strong>${billet.numero_depart}</strong></div>
                <div class="ticket-row"><span>Siege:</span><strong class="ticket-siege">${billet.numero_siege}</strong></div>
                <div class="ticket-row"><span>Ligne:</span><span>${billet.ligne}</span></div>
                <div class="ticket-row"><span>Date:</span><span>${billet.date_depart}</span></div>
                <div class="ticket-row"><span>Heure:</span><span>${billet.heure_depart}</span></div>
            </div>
            `;
        } else {
            if (msgHtml) html += msgHtml;
        }

        html += `</div>`;
        return html;
    }

    function initApercuTicket(options) {
        const checkboxSouche = document.getElementById(options.checkboxSoucheId);
        const textareaMessage = document.getElementById(options.textareaMessageId);
        const container = document.getElementById(options.containerId);
        const compagnieNom = options.compagnieNom || '';
        const compagnieLogo = options.compagnieLogo || '';

        function rafraichir() {
            const billet = billetDemo(
                checkboxSouche ? checkboxSouche.checked : false,
                textareaMessage ? textareaMessage.value : '',
                compagnieNom,
                compagnieLogo
            );
            container.innerHTML = rendreTicketHTML(billet);
        }

        if (checkboxSouche) checkboxSouche.addEventListener('change', rafraichir);
        if (textareaMessage) textareaMessage.addEventListener('input', rafraichir);

        rafraichir();
    }

    window.initApercuTicket = initApercuTicket;
})();
