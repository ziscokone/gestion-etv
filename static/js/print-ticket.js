/**
 * Impression physique d'un ou plusieurs billets sur l'imprimante thermique
 * ESC/POS du poste guichet (voir apps/guichet/impression.py côté serveur).
 *
 * Le poste guichet fait tourner le navigateur ET le serveur Django sur la
 * même machine, avec l'imprimante branchée en USB sur ce même poste : on
 * imprime donc directement depuis Python (python-escpos, backend Win32Raw),
 * sans passer par une boîte de dialogue navigateur. Il n'y a plus de repli
 * navigateur en cas d'échec : l'utilisateur voit un message d'erreur avec un
 * bouton "Réessayer l'impression".
 *
 * L'aperçu HTML à l'écran (.ticket-preview, displayTickets/displayDuplicata
 * dans les templates) reste inchangé : seul le mécanisme d'impression
 * physique est remplacé ici.
 */

async function imprimerBillets(publicIds, csrfToken, { duplicata = false } = {}) {
    const formData = new FormData();
    publicIds.forEach((id) => formData.append('public_id', id));
    formData.append('duplicata', duplicata ? 'true' : 'false');

    let data;
    try {
        const reponse = await fetch('/api/imprimer-billets/', {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': csrfToken },
        });
        data = await reponse.json();
    } catch (e) {
        afficherErreurImpression('Erreur de connexion au serveur.', () =>
            imprimerBillets(publicIds, csrfToken, { duplicata })
        );
        return;
    }

    if (!data.success) {
        afficherErreurImpression(data.error || 'Erreur lors de l\'impression.', () =>
            imprimerBillets(publicIds, csrfToken, { duplicata })
        );
    }
}

function afficherErreurImpression(message, reessayer) {
    const bandeau = document.createElement('div');
    bandeau.className = 'alert alert-danger alert-dismissible fade show position-fixed';
    bandeau.style.top = '1rem';
    bandeau.style.right = '1rem';
    bandeau.style.zIndex = '2000';
    bandeau.style.maxWidth = '400px';

    const texte = document.createElement('span');
    texte.textContent = message;
    bandeau.appendChild(texte);

    const btnReessayer = document.createElement('button');
    btnReessayer.type = 'button';
    btnReessayer.className = 'btn btn-sm btn-outline-light ms-3';
    btnReessayer.textContent = 'Réessayer l\'impression';
    btnReessayer.onclick = () => {
        bandeau.remove();
        reessayer();
    };
    bandeau.appendChild(btnReessayer);

    const btnFermer = document.createElement('button');
    btnFermer.type = 'button';
    btnFermer.className = 'btn-close';
    btnFermer.setAttribute('data-bs-dismiss', 'alert');
    btnFermer.onclick = () => bandeau.remove();
    bandeau.appendChild(btnFermer);

    document.body.appendChild(bandeau);
}
