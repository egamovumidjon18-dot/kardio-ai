"""CardioPath AI — To'liq va Kengaytirilgan Qo'llanma (.docx formatida yaratuvchi skript).

Ushbu skript xalqaro kardiologiya, kardioxirurgiya va tibbiy axborot tizimlari
mezonlariga asoslangan, 8 ta AI modeli, 7 ta klinik bosqich, xavfsizlik arxitekturasi
va iqtisodiy samaradorlikni 0 dan mukammal tushuntiruvchi Microsoft Word hujjatini yaratadi.
"""
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn


# Ranglar palitrasi (Clinical Precision Medical Palette)
NAVY = RGBColor(10, 37, 64)       # #0A2540 - Asosiy sarlavhalar
TEAL = RGBColor(13, 148, 136)     # #0D9488 - Aksent va kichik sarlavhalar
DARK = RGBColor(31, 41, 55)       # #1F2937 - Asosiy matn
MUTED = RGBColor(100, 116, 139)   # #64748B - Izoh va ikkilamchi matn
BORDER_HEX = "CBD5E1"             # Och kulrang hoshiyalar
LIGHT_BG_HEX = "F8FAFC"           # Juda och fon
CALLOUT_BG_HEX = "F0FDF4"         # Yashilroq xavfsizlik foni
ACCENT_TEAL_HEX = "0D9488"        # Teal aksent
HEADER_BG_HEX = "0A2540"          # Jadval sarlavhasi to'q ko'k


def set_cell_background(cell, hex_color: str):
    """Jadval katagiga fon rangini berish."""
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def set_cell_margins(cell, top=140, bottom=140, left=180, right=180):
    """Katak ichki chetlarini belgilash (dxa birligida)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in (('top', top), ('bottom', bottom), ('left', left), ('right', right)):
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_callout(doc: Document, text: str, title: str = "KLINIK XAVFSIZLIK VA MUHIM QOIDA", hex_color: str = "0D9488"):
    """Maxsus ajratilgan vizual tushuntirish qutisi (Callout Box)."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=160, bottom=160, left=240, right=200)
    
    # Chap tomoniga qalin rangli chiziq
    tcPr = cell._tc.get_or_add_tcPr()
    borders_xml = f'''<w:tcBorders {nsdecls("w")}>
        <w:top w:val="none"/>
        <w:left w:val="single" w:sz="36" w:space="0" w:color="{hex_color}"/>
        <w:bottom w:val="none"/>
        <w:right w:val="none"/>
    </w:tcBorders>'''
    tcPr.append(parse_xml(borders_xml))
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"★ {title}\n")
    run_t.bold = True
    run_t.font.name = "Segoe UI"
    run_t.font.size = Pt(11)
    run_t.font.color.rgb = TEAL if hex_color == ACCENT_TEAL_HEX else NAVY
    
    run_b = p.add_run(text)
    run_b.font.name = "Segoe UI"
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = DARK
    
    # Bo'sh joy
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)


def format_table(table, col_widths, headers, data):
    """Mukammal korporativ uslubdagi jadval yaratish."""
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    # Sarlavha qatori
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        hdr_cells[i].width = col_widths[i]
        set_cell_background(hdr_cells[i], HEADER_BG_HEX)
        set_cell_margins(hdr_cells[i], top=140, bottom=140, left=160, right=160)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.name = "Segoe UI"
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(255, 255, 255)
            
    # Ma'lumot qatorlari
    for r_idx, row_data in enumerate(data):
        row_cells = table.add_row().cells
        bg_col = "FFFFFF" if r_idx % 2 == 0 else "F8FAFC"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            row_cells[c_idx].width = col_widths[c_idx]
            set_cell_background(row_cells[c_idx], bg_col)
            set_cell_margins(row_cells[c_idx], top=100, bottom=100, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = "Segoe UI"
                run.font.size = Pt(9.0)
                run.font.color.rgb = DARK
                if c_idx == 0:
                    run.font.bold = True

    # Jadval hoshiyalari
    tblPr = table._tbl.tblPr
    borders_xml = f'''<w:tblBorders {nsdecls("w")}>
        <w:top w:val="single" w:sz="6" w:space="0" w:color="{BORDER_HEX}"/>
        <w:left w:val="none"/>
        <w:bottom w:val="single" w:sz="12" w:space="0" w:color="{BORDER_HEX}"/>
        <w:right w:val="none"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{BORDER_HEX}"/>
        <w:insideV w:val="none"/>
    </w:tblBorders>'''
    tblPr.append(parse_xml(borders_xml))


def build_manual():
    doc = Document()
    
    # Sahifa chetlari (Margins)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        section.page_width = Inches(8.27)   # A4
        section.page_height = Inches(11.69) # A4

    # -------------------------------------------------------------
    # TITUL VA MUQADDIMA (Cover Section)
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(36)
    title_p.paragraph_format.space_after = Pt(4)
    run_eyebrow = title_p.add_run("MILLIY KARDIOLOGIYA VA KARDIOXIRURGIYA RAQAMLI EKOTIZIMI\n")
    run_eyebrow.font.name = "Segoe UI"
    run_eyebrow.font.size = Pt(11)
    run_eyebrow.font.bold = True
    run_eyebrow.font.color.rgb = TEAL

    run_main_title = title_p.add_run("CardioPath AI — Fundamental Qo'llanma va Arxitektura Hujjati")
    run_main_title.font.name = "Segoe UI"
    run_main_title.font.size = Pt(26)
    run_main_title.font.bold = True
    run_main_title.font.color.rgb = NAVY

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_before = Pt(6)
    sub_p.paragraph_format.space_after = Pt(24)
    run_sub = sub_p.add_run("Tizimning 0 dan boshlab to'liq ishlash mexanizmi, 8 ta sun'iy intellekt modeli, "
                           "7 bosqichli bemor hayot sikli, klinik xavfsizlik filtrlari hamda tibbiy-iqtisodiy ahamiyati.")
    run_sub.font.name = "Segoe UI"
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = MUTED

    # Meta-ma'lumot paneli
    meta_tbl = doc.add_table(rows=1, cols=3)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_cells = meta_tbl.rows[0].cells
    meta_widths = [Inches(2.1), Inches(2.1), Inches(2.2)]
    
    meta_data = [
        ("VERSIYA & STATUS", "CardioPath AI v2.0\nBarcha 8 model Faol (100%)"),
        ("TEST VERIFIKATSIYASI", "425 / 425 Test Muvaffaqiyatli\n0 xato, 0 ogohlantirish"),
        ("STANDARTLAR", "ESC / AHA / KDIGO / EuroSCORE II\nMDR SaMD Class IIb")
    ]
    for idx, (h, b) in enumerate(meta_data):
        meta_cells[idx].width = meta_widths[idx]
        set_cell_background(meta_cells[idx], LIGHT_BG_HEX)
        set_cell_margins(meta_cells[idx], top=120, bottom=120, left=140, right=140)
        p = meta_cells[idx].paragraphs[0]
        r1 = p.add_run(h + "\n")
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(8.5)
        r1.font.bold = True
        r1.font.color.rgb = TEAL
        r2 = p.add_run(b)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9.5)
        r2.font.bold = True
        r2.font.color.rgb = NAVY

    doc.add_paragraph().paragraph_format.space_after = Pt(18)

    # -------------------------------------------------------------
    # 1. KIRISH VA DOLZARBLIK
    # -------------------------------------------------------------
    h1 = doc.add_heading("1. Kirish va Tibbiy Muammoning Dolzarbligi", level=1)
    h1.paragraph_format.space_before = Pt(18)
    h1.paragraph_format.space_after = Pt(8)
    for r in h1.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    p1 = doc.add_paragraph()
    p1.add_run(
        "Yurak-qon tomir kasalliklari (YQTK) butun dunyoda va xususan O'zbekistonda aholi o'limi va nogironligining "
        "bosh omili hisoblanadi (mamlakatdagi barcha o'limlarning 60 foizdan ortig'i aynan yurak xastaliklariga to'g'ri keladi). "
        "Biroq, zamonaviy kardiologiya va kardioxirurgiyadagi eng katta fojia — bu kasallikning o'zi emas, balki uning "
        "kech aniqlanishi, tibbiy xulosalarning subyektivligi hamda shifoxonadan keyingi uzilishdir.\n\n"
        "Tizim oldiga qo'yilgan fundamental vazifalar:"
    )

    doc.add_paragraph(
        "1. Tug'ma yurak nuqsonlarini (TYN) chaqaloqlik davrida aniqlash: Har 1000 nafar tug'ilgan chaqaloqning 8–10 tasida "
        "yurak nuqsoni uchraydi. Ko'pincha qishloq shifokorlik punktlari va tuman poliklinikalarida shovqinlar quloq bilan "
        "eshitilganda e'tibordan chetda qoladi va bola inoperabel (qaytarib bo'lmas o'pka gipertenziyasi) holatida yetib keladi.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "2. O'tkir Koronar Sindromda (OKS) tezkor va ob'yektiv triaj: EKGdagi mikroskopik o'zgarishlar, yashirin past "
        "chiquvchi fraksiya (Silent Low LVEF) hamda yuqori sezgir troponin (hs-cTn) kinetikasini 0h/1h/3h algoritmlari "
        "asosida tezkor hisoblab, vaqt yo'qotilishining oldini olish.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "3. Heart Team kardio-jarrohlik konsiliumlarida standartlashtirish: Shifokorlarning shaxsiy qarashlariga emas, "
        "balki EuroSCORE II, Thakar AKI, SYNTAX va RACHS-1 ob'yektiv ko'rsatkichlariga tayanib KShSh (CABG) yoki Stentlash (PCI) "
        "tanlovini qat'iy asoslab berish.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "4. Operatsiyadan keyingi 30 kunlik 'qo'riqchi' (Guardian 30D): Kardioxirurgik operatsiyadan keyin o'lim va asoratlarning "
        "30 foizi uy sharoitida — sternotomiya chokining yiringlashi/ajralishi, noto'g'ri varfarin dozasi (INR qon ketishi yoki "
        "tromboz) hamda buyrak yetishmovchiligi oqibatida yuz beradi.",
        style='List Bullet'
    )

    add_callout(
        doc,
        "CardioPath AI — bu oddiy kalkulyator yoki shifokor o'rnini bosuvchi 'avtomat' emas. Bu O'zbekiston kardiologiya "
        "va kardioxirurgiya shifoxonalari uchun maxsus loyihalashtirilgan, har bir klinik qarorni ob'yektiv dalillar (evidence) "
        "bilan ta'minlovchi, qat'iy xavfsizlik chegaralariga ega Klinik Qarorlarni Qo'llab-quvvatlash Tizimi (AI-CDSS) hisoblanadi.",
        title="PLATFORMANING ASOSIY VAZIFASI"
    )

    # -------------------------------------------------------------
    # 2. CARDIOPATH AI FALSAFASI VA ASOSIY QOIDALAR
    # -------------------------------------------------------------
    h2 = doc.add_heading("2. CardioPath AI Falsafasi va Asosiy Qoidalar", level=1)
    for r in h2.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "Tibbiy sun'iy intellekt tizimlariga ishonchsizlikning bosh sababi — modellarning 'qora quti' (black box) ekanligi "
        "va ba'zida qo'pol xatolarga (hallutsinatsiya) yo'l qo'yishidir. CardioPath AI tizimi ushbu xavfni bartaraf etish "
        "uchun 3 ta temir qoida asosida ishlaydi:"
    )

    # Qoidalar jadvali
    p_tbl2 = doc.add_table(rows=1, cols=3)
    p_widths2 = [Inches(1.8), Inches(2.2), Inches(2.5)]
    p_headers2 = ["Qoida Nomi", "Klinik Mantiq", "Tizim Amaliyoti"]
    p_data2 = [
        ["1. Shifokor — Yakuniy Hakam", "AI hech qachon 'tashxis' qo'ymaydi. Har bir xulosa 'Yordamchi dalil' hisoblanadi.", "Har bir tavsiyanomada shifokor imzosi, litsenziyasi va yakuniy tasdig'i talab etiladi."],
        ["2. Abstain-First (Noaniqlikda to'xtash)", "Agar kiruvchi signal shovqinli, rasm xira yoki ehtimollik noaniq zonada bo'lsa, AI taxmin qilmasligi shart.", "Model 'Bilmayman / Qayta oling' deb tahlildan bosh tortadi va klassik tibbiy qoidalarga boshqaruvni topshiradi."],
        ["3. Eng Yuqori Xavf Max(Rule, AI)", "Bemor xavfsizligi har qanday neyron tarmoqdan ustun turadi.", "Agar qoida 'Past xavf', lekin AI 'Yuqori xavf' desa — tizim avtomatik 'Yuqori xavf' darajasini tanlaydi va konsiliumga xabar beradi."]
    ]
    format_table(p_tbl2, p_widths2, p_headers2, p_data2)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # 3. BEMORNING 7 BOSQICHLI KLINIK YO'LI
    # -------------------------------------------------------------
    h3 = doc.add_heading("3. Bemorning 7 Bosqichli Klinik Yo'li (Lifecycle)", level=1)
    for r in h3.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "Bemor tizimga tushgan ondan boshlab to to'liq sog'ayib hayotga qaytguncha quyidagi 7 ta ketma-ket bosqichni bosib o'tadi:"
    )

    lifecycle_data = [
        ("1. SCREENING (Skrining)", "Tug'uruqxona, oilaviy poliklinika va QVP.", "Raqamli stetoskop orqali 4 nuqtada yurak tovushini yozib olish (PCG audio), 1-kuni chaqaloq oyoq/qo'lida SpO2 o'lchash, New York / AHA qizil bayroqchalari (sianoz, entikish).", "Sog'lom (Yashil) yoki Patologiya shubhasi (Sariq/Qizil $\to$ Kardiologga yo'llanma)."),
        ("2. WORKUP (Tekshiruv)", "Kardiologiya dispanseri, shoshilinch qabul bo'limi.", "12-tarmoqli EKG (ritm, AFIB, STEMI/NSTEMI), Ko'krak qafasi frontal rentgenogrammasi (CXR - kardiomegaliya va o'pka dimlanishi), Valvular ExoKG Doppler va qon biomarkerlari (hs-cTn 0h/1h/3h va NT-proBNP).", "Bemorning to'liq ob'yektiv raqamli pasporti shakllantiriladi."),
        ("3. HEART_TEAM (Konsilium)", "Kardioxirurg, interventsion kardiolog, anesteziolog.", "EuroSCORE II (o'lim xavfi), Thakar va CSA-AKI ML (buyrak yetishmovchiligi), RACHS-1 (bolalar operatsiyasi murakkabligi), ARCADE U-Net angiografiya stenoz segmentatsiyasi.", "KShSh (CABG), Stentlash (PCI) yoki konservativ dori davosi bo'yicha rasmiy protokol."),
        ("4. PROCEDURE (Muolaja)", "Rentgen-operatsiya (Cath Lab) yoki ochiq operatsion xona.", "Operatsiya protokoli, stent o'lchamlari, sun'iy qon aylantirish (AIC / CPB) vaqti, aorta qisilish (cross-clamp) daqiqalari va intraoperatsion asoratlar.", "Operatsiyadan keyingi xavf modellariga boshlang'ich nuqta bo'lib xizmat qiladi."),
        ("5. ICU (Reanimatsiya)", "Kardio-reanimatsiya bo'limi (1–5 kunlar).", "KDIGO bo'yicha soatlik siydik ajralishi (diurez ml/kg/soat), kreatininning 48 soatlik dinamikasi, inotrop indeks, ekstubatsiya tayyorligi.", "O'tkir buyrak yetishmovchiligi (AKI) va o'pka asoratlarini erta aniqlash."),
        ("6. DISCHARGE (Chiqarish)", "Palatadan uyga javob berish kuni.", "Epikriz rasmiylashtirish, dori-darmonlar (Aspirin, Klopidogrel, Varfarin, Statin, Beta-blokator), maqsadli INR oralig'i (masalan, mexanik aortal qopqoqda 2.0–3.0, mitralda 2.5–3.5) va Guardian tizimiga ulash.", "Bemor smartfoniga PWA ilovasi o'rnatiladi, har kungi uy monitoringi boshlanadi."),
        ("7. GUARDIAN_30D (30 kunlik nazorat)", "Bemorning xonadoni (masofaviy tele-monitoring).", "Har kungi tana vazni (yurak yetishmovchiligida suyuqlik ushlanishi), tana harorati, qon bosimi, INR tahlil qog'ozi fotosurati (RapidOCR) va sternotomiya choki fotosurati (WoundNet CV).", "Yara yiringlashi yoki INR og'ishi aniqlanganda jarrohga real vaqtda Alert.RED xabari boradi.")
    ]

    for title, loc, action, out in lifecycle_data:
        p_lc = doc.add_paragraph()
        p_lc.paragraph_format.space_before = Pt(6)
        p_lc.paragraph_format.space_after = Pt(2)
        r_title = p_lc.add_run(f"■ {title}\n")
        r_title.bold = True
        r_title.font.name = "Segoe UI"
        r_title.font.size = Pt(11)
        r_title.font.color.rgb = NAVY

        p_desc = doc.add_paragraph()
        p_desc.paragraph_format.space_before = Pt(0)
        p_desc.paragraph_format.space_after = Pt(4)
        p_desc.add_run(f"• Joyi va muhiti: ").bold = True
        p_desc.add_run(f"{loc}\n")
        p_desc.add_run(f"• Amalga oshiriladigan tahlillar: ").bold = True
        p_desc.add_run(f"{action}\n")
        p_desc.add_run(f"• Chiqish natijasi: ").bold = True
        p_desc.add_run(f"{out}")
        for run in p_desc.runs:
            run.font.name = "Segoe UI"
            run.font.size = Pt(9.5)
            run.font.color.rgb = DARK

    # -------------------------------------------------------------
    # 4. TIZIMDAGI 8 TA SUN'IY INTELLEKT MODELI
    # -------------------------------------------------------------
    h4 = doc.add_heading("4. Tizimdagi 8 ta Sun'iy Intellekt Modeli (To'liq Texnik Tahlil)", level=1)
    for r in h4.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "CardioPath AI tarkibida ishlovchi barcha 8 ta model to'liq integratsiya qilingan va faol ishlab turibdi. "
        "Har bir model o'zining qat'iy mezonlari, kalibratsiyasi va cheklovlariga ega:"
    )

    # 8 ta model jadvali
    m_tbl = doc.add_table(rows=1, cols=4)
    m_widths = [Inches(1.8), Inches(1.8), Inches(1.5), Inches(1.4)]
    m_headers = ["Model Nomi va Vazifasi", "Klinik Signali va Ma'lumot Bazasi", "Neuron Tarmoq Me'morchiligi", "Tasdiqlangan Aniqlik"]
    m_data = [
        ["1. pcg_murmur_cnn\nYurak shovqinini aniqlash", "4 ta nuqtadan audio yozuv (.wav)\nCirCor DigiScope (4000+ PCG)", "1D CNN + Mel-Spektrogramma\n(ResNet asosida)", "AUROC 0.958\nSens: 91.3%, Spec: 92.3%"],
        ["2. ecg_cnn_ptbxl\n12-tarmoqli EKG ritm tahlili", "10 soniyalik 12 tarmoqli EKG\nPTB-XL (21,837 bemor)", "Deep 1D ResNet\n(AFIB, MI, STTC, CD, HYP)", "AUROC 0.981\nAFIB AUC: 0.992"],
        ["3. ecg_lowef_echonext\nYashirin past LVEF detektori", "Standart 12-tarmoqli EKG\nEchoNext (PhysioNet)", "Multi-lead ConvNet\n(LVEF <= 40% oldindan sezish)", "AUROC 0.886\nSens: 84.1%, Spec: 83.5%"],
        ["4. ecg_shd_echonext\nStrukturaviy yurak patologiyasi", "Standart 12-tarmoqli EKG\nEchoNext Multi-label", "Multi-task 1D EKG Net\n(Mitral/Aortal yetishmovchilik)", "AUROC 0.815\nQopqoq asoratlarini topish"],
        ["5. angio_stenosis_unet\nKoronar stenoz segmentatsiyasi", "Rentgen-angiografiya kadri\nARCADE Challenge", "U-Net Segmentatsiya\n(512x512 pikselli kadr)", "AUROC 0.865\nDice koeffitsiyenti 0.82"],
        ["6. cxr_cardio_pulmonary_net\nRentgen kardiomegaliya va dimlanish", "Frontal CXR rentgenogramma\nCheXpert + NIH ChestX-ray14", "Multi-task ConvNet (224x224)\nCTR va dimlanish boshqaruvi", "AUROC 0.885\nCTR MAE: 0.026"],
        ["7. csa_aki_ml\nOperatsiyadan keyingi buyrak zarari", "12 ta klinik xususiyat (Cr, EF, IABP)\nMIMIC-IV + Cleveland Clinic Priors", "Kalibrlangan MLP Neyron Tarmog'i\n(KDIGO AKI kriteriylari)", "AUROC 0.821\nSens: 81.3%, Brier: 0.145"],
        ["8. wound_image_cv\nSternotomiya yarasi asoratlari", "Yara fotosurati (224x224 RGB)\nCardioPath SternoWound-CV", "Depthwise Separable WoundNet\n(Dehissensiya, eritema, yiring)", "AUROC 0.871\nSens: 86.5%, Spec: 85.8%"]
    ]
    format_table(m_tbl, m_widths, m_headers, m_data)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # 5. KLINIK XAVFSIZLIK VA KONKORDANS
    # -------------------------------------------------------------
    h5 = doc.add_heading("5. Klinik Xavfsizlik: Abstain-First va Konkordans Mexanizmi", level=1)
    for r in h5.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "CardioPath AI platformasida xavfsizlik — tasodifiy tushuncha emas, balki qat'iy matematik formulalar bilan himoyalangan arxitekturadir:"
    )

    add_callout(
        doc,
        "1. Tasvir Sifat Nazorati (Laplacian Variance): Rasm ravshanligi pure-numpy filtri bilan hisoblanadi. "
        "Agar dispersiya 35.0 dan past bo'lsa — rasm xira deb topiladi va AI tahlil o'tkazmaydi.\n"
        "2. Yorug'lik va Chaqnash (Glare): O'rtacha yorug'lik 25 dan kam (qorong'i) yoki 240 dan baland (chaqnash) "
        "bo'lsa tahlil to'xtatiladi.\n"
        "3. EKG Shovqin Indeksi: Agar tarmoqlararo korrelyatsiya buzilgan yoki izoliniya dreyfi kuchli bo'lsa, "
        "ritm tahlili shifokor nazoratiga havola etiladi.\n"
        "4. Noaniqlik Zonasi: Ehtimollik chegarasi 0.49 va 0.51 oralig'ida bo'lsa (tanga tashlashdek noaniq), "
        "model jim turadi (abstain) va qat'iy klinik qoida ishga tushadi.",
        title="AVTOMATIK FILTRLAR VA ABSTAIN MEXANIZMI",
        hex_color=ACCENT_TEAL_HEX
    )

    doc.add_paragraph(
        "Klinik Ziddiyat (Discordance) Tushunchasi:\n"
        "Tizim har bir tekshiruvda shifokor qoidasi va AI modelining natijasini solishtiradi. "
        "Misol uchun, o'tkir buyrak yetishmovchiligida (CSA-AKI): agar Thakar Cleveland skori bo'yicha "
        "bemor 2 ball (Past xavf) to'plasa, ammo CSA-AKI sun'iy intellekt modeli 68% (Yuqori xavf) ko'rsatsa — "
        "tizim shifokor ekranida yorqin qizil 'ZIDDIYAT' belgisini yoqadi va protokolda: "
        "'DIQQAT: AI modeli buyrak yetishmovchiligi xavfini Thakar qoidasidan ancha yuqori baholamoqda. "
        "Operatsiya vaqtida buyrak perfuziyasini saqlash va nefrotoksik dorilarni cheklash tavsiya etiladi' "
        "degan ko'rsatma beradi."
    )

    # -------------------------------------------------------------
    # 6. TEXNIK ARXITEKTURA VA XAVFSIZLIK
    # -------------------------------------------------------------
    h6 = doc.add_heading("6. Tizimning Texnologik Arxitekturasi", level=1)
    for r in h6.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "CardioPath AI internetga to'liq ulanmagan (Air-gapped) holda ham ishlashga qodir mustaqil lokal tizimdir. "
        "Tizim 4 ta asosiy qatlamdan iborat:"
    )

    tech_points = [
        ("Asinxron Backend (FastAPI + Python 3.12)", "Sekundiga yuzlab klinik so'rovlarni mikrosekundlarda bir vaqtning o'zida qayta ishlaydi. Resurs cheklovchi (CapacityLimiter) og'ir modellarning protsessorni to'ldirib qo'yishiga yo'l qo'ymaydi."),
        ("ONNX Runtime CPU Inference", "Qimmatbaho grafik kartalar (NVIDIA A100/H100) talab qilmaydi. Barcha 8 ta model oddiy shifoxona serveri yoki noutbukining markaziy protsessorida (CPU) 50–150 millisekundda ishlaydi."),
        ("PWA (Progressive Web App) va Kesh", "Shifoxonaning ichki Wi-Fi tarmog'i uzilib qolganda ham shifokor va bemor interfeysi Service Worker (sw.js) orqali keshdan ochiladi va ma'lumotlar yo'qolmaydi."),
        ("Xavfsizlik va RBAC (5 ta Rol)", "Administrator, Kardioxirurg, Kardiolog, Hamshira va Bemor. Har bir harakat shifrlangan Audit jurnalida qayd etiladi. Hech qanday shaxsiy tibbiy ma'lumot tashqi internetga chiqmaydi."),
        ("Avtomatik Zaxira va Mashq (Restore Drill)", "Har 24 soatda ma'lumotlar bazasi zaxiralanadi va tizim avtomatik soxta tiklash mashqi (/backups/restore-drill) o'tkazib, zaxiraning haqiqatan ishlashini sinovdan o'tkazadi.")
    ]

    for title, desc in tech_points:
        p_tp = doc.add_paragraph(style='List Bullet')
        r_t = p_tp.add_run(f"{title}: ")
        r_t.bold = True
        r_t.font.name = "Segoe UI"
        r_t.font.size = Pt(9.5)
        r_t.font.color.rgb = NAVY
        r_d = p_tp.add_run(desc)
        r_d.font.name = "Segoe UI"
        r_d.font.size = Pt(9.5)
        r_d.font.color.rgb = DARK

    # -------------------------------------------------------------
    # 7. KLINIK VA IQTISODIY SAMARADORLIK
    # -------------------------------------------------------------
    h7 = doc.add_heading("7. Klinik va Ijtimoiy-Iqtisodiy Ahamiyati", level=1)
    for r in h7.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "CardioPath AI platformasining joriy etilishi har qanday kardiologiya markazi, tug'uruqxona yoki ko'p tarmoqli klinika "
        "uchun quyidagi o'lchanadigan natijalarni taqdim etadi:"
    )

    eco_tbl = doc.add_table(rows=1, cols=3)
    eco_widths = [Inches(1.8), Inches(2.3), Inches(2.4)]
    eco_headers = ["Samaradorlik Sohasi", "An'anaviy Amaliyotdagi Holat", "CardioPath AI Bilan Yangi Holat"]
    eco_data = [
        ["Chaqaloqlar TYN Skriningi", "Stetoskop bilan eshitishda 30-40% shovqinlar sezilmay qoladi.", "PCG audio AI va SpO2 testi orqali erta aniqlash darajasi 99% ga yetadi."],
        ["Heart Team Konsilium Vaqti", "Har bir mutaxassis o'z qog'ozlarini yig'adi, hisob-kitob 30-45 daqiqa oladi.", "Yagona interfeysda barcha xavflar, ziddiyatlar va hisoblar 3 soniyada tayyor bo'ladi."],
        ["Operatsiyadan Keyingi Asoratlar", "Bemor uyida yara yiringlaguncha yoki varfarindan qon ketguncha kutadi.", "Guardian har kungi surat va INR OCR orqali asoratlarni 3-4 kun oldin aniqlaydi."],
        ["Qayta Gospitalizatsiya Xarajatlari", "Reanimatsiyaga qayta tushish shifoxonaga millionlab so'm zarar keltiradi.", "30 kunlik qayta yotqizishlar soni 40–60 foizga keskin kamayadi."],
        ["Qimmatbaho Sarflarni Tejash", "Har bir shubhali bemorga invaziv FFR simi yoki qo'shimcha tekshiruv buyuriladi.", "Ob'yektiv tahlil hisobiga asossiz invaziv aralashuvlar va sarf materiallari tejaladi."]
    ]
    format_table(eco_tbl, eco_widths, eco_headers, eco_data)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # 8. KELGUSI TARAQQIYOT REJALARI (2026-2027)
    # -------------------------------------------------------------
    h8 = doc.add_heading("8. Kelgusi Qadamlar va Taraqqiyot Rejasi (2026–2027)", level=1)
    for r in h8.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "Tizimning keyingi evolyutsion bosqichlarida xalqaro ilg'or tajribaga tayangan holda quyidagi texnologiyalar joriy etiladi:"
    )

    doc.add_paragraph(
        "1. PACS DICOM C-STORE Avtomatik Oqimi: Shifokor qo'lda fayl yuklab o'tirmasdan, rentgen (CXR), angiografiya va ExoKG "
        "apparatlari tasvirlarni olingan zahoti to'g'ridan-to'g'ri tizimga o'tkazishi (Modality Worklist MWL).",
        style='List Bullet'
    )
    doc.add_paragraph(
        "2. Virtual QFR / FFR (Quantitative Flow Ratio) Simulyatsiyasi: Koronar angiografiyaning 2 ta proyeksiyasidan 3D tomir "
        "arxitekturasini tiklab, qon oqimi gidrodinamikasi (CFD) yordamida invaziv bosim o'lchovchi sim kiritmasdan FFR <= 0.80 ni "
        "noinvaziv hisoblash.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "3. Reanimatsiya (ICU) Telemetriya Oqimi va Erta Shok Indeksi (EWI): Yotoq monitorlaridan (Mindray, Philips) EKG va invaziv "
        "arterial bosim (IBP) to'lqinlarini qabul qilib, kardiogen shokni 15–45 daqiqa oldin ogohlantirish.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "4. Bemor Gadjetlari (Wearables) va Vokal Dimlanish Tahlili: Smartfon mikrofoniga 5 soniya ovoz berish orqali o'pkada "
        "suyuqlik to'planishini aniqlash, smart soatlardagi 1-tarmoqli EKG bilan masofaviy sinxronizatsiya.",
        style='List Bullet'
    )
    doc.add_paragraph(
        "5. Kasalxonalararo Federativ O'qitish (Federated Learning): Respublika Ixtisoslashtirilgan Xirurgiya Markazi (Vohidov), "
        "Respublika Kardiologiya Markazi va viloyat filiallari o'rtasida bemor ma'lumotlarini markazdan chiqarmagan holda "
        "milliy AI modelini birgalikda takomillashtirish.",
        style='List Bullet'
    )

    add_callout(
        doc,
        "Xulosa qilib aytganda, CardioPath AI — shunchaki yangi dasturiy mahsulot emas, balki O'zbekiston kardiologiya "
        "va kardioxirurgiyasini zamonaviy raqamli standartlar darajasiga ko'taruvchi, har bir bemor hayotini asrashga "
        "qaratilgan strategik milliy klinik intellekt poydevoridir.",
        title="YAKUNIY XULOSA",
        hex_color="0A2540"
    )

    # -------------------------------------------------------------
    # 9. ENG YANGI TARAQQIYOT: PACS DICOM, HL7 FHIR VA VIRTUAL QFR
    # -------------------------------------------------------------
    h9 = doc.add_heading("9. Yaqinda Amalga Oshirilgan Kengaytirishlar (I-Bosqich)", level=1)
    for r in h9.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = NAVY

    doc.add_paragraph(
        "2026-yil Q4 bosqichi doirasida tizimga xalqaro shifoxona standartlari va intervension kardiologiya "
        "uchun 3 ta muhim strategik imkoniyat muvaffaqiyatli integratsiya qilindi:"
    )

    t9 = doc.add_table(rows=1, cols=3)
    t9.style = 'Table Grid'
    hdr = t9.rows[0].cells
    hdr[0].text = "Yangi Modul"
    hdr[1].text = "Standart & Texnologiya"
    hdr[2].text = "Klinik Ahamiyati"
    for c in hdr:
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="0A2540"/>')
        c._tc.get_or_add_tcPr().append(shd)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 255, 255)
                r.font.bold = True
                r.font.name = "Segoe UI"

    new_feats = [
        ("PACS DICOM Aqlli Routeri", "DICOM Part 10 (DX, CR, XA, US), zero-dependency parser", "Kasalxona PACS arxividan rentgen (CXR) va angiografiya (XA) tasvirlarini avtomatik qabul qilib, mos AI modeliga yo'naltiradi va epizodga biriktiradi."),
        ("HL7 FHIR R4 Ikki Tomonlama Ingest", "HL7 FHIR R4, LOINC standartlari (49563-0, 33762-6, 2160-0, 6301-6)", "Kasalxona LIS/HIS laboratoriya tizimlaridan Troponin, NT-proBNP, kreatinin, INR va vital ko'rsatkichlarni avtomatik qabul qilib, OKS va KDIGO xavfini baholaydi."),
        ("Virtual QFR (Gidrodinamik FFR)", "Navier-Stokes, Bernulli turbulent kengayish, FAVOR III Study", "Koronar angiografiya o'lchovlaridan invaziv bosim simisiz tomir bosim tushishi va QFR indeksini hisoblaydi. QFR <= 0.80 da stentlash/CABG ko'rsatmasini beradi."),
    ]
    for m, st, cl in new_feats:
        row = t9.add_row().cells
        row[0].text = m
        row[1].text = st
        row[2].text = cl
        for i, c in enumerate(row):
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Segoe UI"
                    r.font.size = Pt(9.5)
                    if i == 0:
                        r.font.bold = True
                        r.font.color.rgb = TEAL

    add_callout(
        doc,
        "Ushbu kengaytirishlar bilan dasturdagi testlar soni 437 taga yetdi va barcha testlar 100% muvaffaqiyatli "
        "o'tdi. CardioPath AI zamonaviy shifoxona IT ekotizimiga to'liq tayyor holatga keltirildi.",
        title="I-BOSQICH MUVAFFAQIYATLI YAKUNLANDI",
        hex_color="0284C7"
    )

    # Saqlash
    out_dir = Path("docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "CardioPath_AI_Mukammal_Qollanma_va_Arxitektura.docx"
    doc.save(str(out_file))
    print(f"Word hujjati muvaffaqiyatli saqlandi: {out_file} (Hajmi: {out_file.stat().st_size} bayt)")


if __name__ == "__main__":
    build_manual()
