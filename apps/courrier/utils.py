"""
Génération du bordereau de chargement colis (PDF), sur le même modèle que
apps.comptabilite.utils.export_rapport_gare_pdf.
"""
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _format_montant(value):
    if value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return "0"


def generer_bordereau_pdf(voyage, colis_qs):
    """
    Construit le bordereau de chargement colis d'un voyage : en-tête (gare,
    véhicule, chauffeur, date/heure), tableau des colis, total, et deux
    zones de signature (remis par / reçu par).
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab n'est pas installé. Installez-le avec: pip install reportlab")

    try:
        from apps.compagnie.models import Compagnie
        compagnie = Compagnie.get_instance()
    except Exception:
        compagnie = None

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=1.2*cm, bottomMargin=1.2*cm
    )
    elements = []
    styles = getSampleStyleSheet()
    largeur_utile = 18.1*cm

    # ========== EN-TÊTE ==========
    header_line = Table([['']], colWidths=[largeur_utile])
    header_line.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_line)
    elements.append(Spacer(1, 0.2*cm))

    if compagnie:
        company_style = ParagraphStyle('CompanyStyle', parent=styles['Normal'], fontSize=12,
                                        textColor=colors.HexColor('#2c3e50'), spaceAfter=2)
        elements.append(Paragraph(f"<b>{compagnie.nom}</b>", company_style))

    elements.append(Spacer(1, 0.3*cm))

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=15,
                                  textColor=colors.HexColor('#34495e'), spaceAfter=8,
                                  alignment=1, fontName='Helvetica-Bold')
    elements.append(Paragraph("BORDEREAU DE CHARGEMENT COLIS", title_style))

    # ========== INFOS VOYAGE ==========
    info_bg = Table([['']], colWidths=[largeur_utile], rowHeights=[1.4*cm])
    info_bg.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ecf0f1'))]))
    elements.append(info_bg)
    elements.append(Spacer(1, -1.3*cm))

    vehicule_str = str(voyage.vehicule) if voyage.vehicule else 'Non renseigné'
    chauffeur_str = voyage.chauffeur.nom_complet if voyage.chauffeur else 'Non renseigné'

    info_data = [
        [f"Gare de départ : {voyage.gare.nom}", f"Ligne : {voyage.ligne}"],
        [f"Date/heure de départ : {voyage.date_depart.strftime('%d/%m/%Y')} à {voyage.heure_depart.strftime('%H:%M')}",
         f"N° départ : {voyage.numero_depart}"],
        [f"Véhicule : {vehicule_str}", f"Chauffeur : {chauffeur_str}"],
    ]
    info_table = Table(info_data, colWidths=[largeur_utile/2, largeur_utile/2])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5*cm))

    # ========== TABLEAU DES COLIS ==========
    headers = ['Code colis', 'Destination', 'Expéditeur', 'Destinataire', 'Type', 'Valeur décl.', 'Montant']
    table_data = [headers]

    total_montant = 0
    total_valeur = 0
    for colis in colis_qs:
        total_montant += int(colis.montant or 0)
        if colis.valeur_declaree:
            total_valeur += int(colis.valeur_declaree)
        table_data.append([
            colis.code_colis,
            colis.gare_destination.nom,
            f"{colis.expediteur_nom}\n{colis.expediteur_telephone}",
            f"{colis.destinataire_nom}\n{colis.destinataire_telephone}",
            colis.type_colis.nom,
            f"{_format_montant(colis.valeur_declaree)} FCFA" if colis.valeur_declaree else '-',
            f"{_format_montant(colis.montant)} FCFA",
        ])

    nb_colis = colis_qs.count()
    if nb_colis:
        table_data.append([
            f"TOTAL ({nb_colis} colis)", '', '', '', '',
            f"{_format_montant(total_valeur)} FCFA",
            f"{_format_montant(total_montant)} FCFA",
        ])

    col_widths = [2.9*cm, 2.6*cm, 3.4*cm, 3.4*cm, 2.4*cm, 2.4*cm, 2.4*cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (5, 1), (6, -1), 'RIGHT'),
    ])
    if nb_colis:
        table_style.add('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1'))
        table_style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
    for i in range(1, len(table_data) - (1 if nb_colis else 0)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fa'))
    table.setStyle(table_style)
    elements.append(table)

    if not nb_colis:
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph("Aucun colis chargé sur ce voyage pour le moment.", styles['Italic']))

    # ========== SIGNATURES ==========
    elements.append(Spacer(1, 1.5*cm))
    signature_data = [[
        "Remis par (gare de départ)\n\n\n\n_______________________\nNom, signature, date",
        "Reçu par (gare d'arrivée)\n\n\n\n_______________________\nNom, signature, date",
    ]]
    signature_table = Table(signature_data, colWidths=[largeur_utile/2, largeur_utile/2])
    signature_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(signature_table)

    elements.append(Spacer(1, 0.8*cm))
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=7,
                                   textColor=colors.HexColor('#7f8c8d'), alignment=1)
    elements.append(Paragraph(f"Document généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", footer_style))

    doc.build(elements)
    output.seek(0)

    filename = f"bordereau_colis_{voyage.gare.code}_{voyage.date_depart.strftime('%Y%m%d')}_depart{voyage.numero_depart}.pdf"
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
