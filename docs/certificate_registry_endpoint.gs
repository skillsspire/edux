/**
 * SkillsSpire website -> certificate registry bridge.
 *
 * Add these functions to the existing Apps Script project that owns the
 * certificate registry. Store the shared secret in Script Properties under:
 * CERTIFICATE_REGISTRY_TOKEN
 *
 * Deploy the project as a Web App and use its /exec URL in Vercel as
 * CERTIFICATE_REGISTRY_ENDPOINT.
 */

function doPost(e) {
  try {
    const payload = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const expectedToken = String(
      PropertiesService.getScriptProperties().getProperty('CERTIFICATE_REGISTRY_TOKEN') || ''
    );

    if (!expectedToken || String(payload.token || '') !== expectedToken) {
      return jsonResponse_({ ok: false, error: 'Unauthorized' });
    }

    if (String(payload.source || '') !== 'skillsspire_site') {
      return jsonResponse_({ ok: false, error: 'Unknown source' });
    }

    const localRequestId = String(payload.local_request_id || '').trim();
    const email = String(payload.email || '').trim();
    const course = String(payload.course || '').trim();
    const hours = Number(payload.hours || 0);
    const periodMode = String(payload.period_mode || 'without_period').trim();
    const callbackUrl = String(payload.callback_url || '').trim();

    if (callbackUrl) {
      PropertiesService.getScriptProperties().setProperty('SKILLSSPIRE_CALLBACK_URL', callbackUrl);
    }

    if (!localRequestId || !email || !course || !hours) {
      return jsonResponse_({ ok: false, error: 'Missing required fields' });
    }

    const requestId = 'SITE-' + localRequestId;
    const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);

    const lastRow = sh.getLastRow();
    if (lastRow >= 2) {
      const ids = sh.getRange(2, COL.ID, lastRow - 1, 1).getDisplayValues().flat();
      if (ids.indexOf(requestId) !== -1) {
        return jsonResponse_({ ok: true, request_id: requestId, duplicate: true });
      }
    }

    const surname = String(payload.surname || '').trim();
    const name = String(payload.name || '').trim();
    const fullName = String(payload.full_name || [surname, name].filter(Boolean).join(' ')).trim();

    let startDate = '';
    let endDate = '';
    if (periodMode === 'with_period') {
      startDate = parseIsoDate_(payload.start_date);
      endDate = parseIsoDate_(payload.end_date);
      if (!startDate || !endDate) {
        return jsonResponse_({ ok: false, error: 'Period dates are required' });
      }
    }

    sh.appendRow([
      requestId,
      new Date(),
      surname,
      name,
      '',
      fullName,
      email,
      course,
      hours,
      startDate,
      endDate,
      'На проверке',
      false,
      '',
      '',
      '',
      '',
      '',
      '',
      false,
      String(payload.language || 'Русский')
    ]);

    return jsonResponse_({
      ok: true,
      request_id: requestId,
      period_mode: periodMode
    });
  } catch (err) {
    console.error(err);
    return jsonResponse_({ ok: false, error: String(err && err.message ? err.message : err) });
  }
}

function parseIsoDate_(value) {
  const text = String(value || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return '';
  const parts = text.split('-').map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function jsonResponse_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * Call this after a certificate created from a SITE-* registry row is issued.
 * The Django site will then show the PDF/number in the learner cabinet.
 */
function notifySiteCertificateIssued_(requestId, regNumber, pdfUrl, verifyUrl) {
  const requestText = String(requestId || '').trim();
  if (requestText.indexOf('SITE-') !== 0) return;

  const localRequestId = requestText.substring(5);
  if (!localRequestId) return;

  const props = PropertiesService.getScriptProperties();
  const callbackUrl = String(props.getProperty('SKILLSSPIRE_CALLBACK_URL') || '').trim();
  const token = String(props.getProperty('CERTIFICATE_REGISTRY_TOKEN') || '').trim();

  if (!callbackUrl || !token) {
    console.warn('SkillsSpire callback URL/token is not configured.');
    return;
  }

  try {
    UrlFetchApp.fetch(callbackUrl, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload: JSON.stringify({
        token: token,
        local_request_id: localRequestId,
        status: 'issued',
        certificate_number: String(regNumber || ''),
        pdf_url: String(pdfUrl || ''),
        verify_url: String(verifyUrl || '')
      })
    });
  } catch (err) {
    console.error('SkillsSpire callback failed: ' + err.message);
  }
}


/**
 * REQUIRED PATCHES IN THE EXISTING v10 SCRIPT
 *
 * 1) OPTIONAL PERIOD
 *
 * In createCertificate_() replace:
 *
 *   if (!startDate || !endDate) {
 *     throw new Error('Перед выдачей заполните в Реестре «Дата начала» и «Дата окончания».');
 *   }
 *
 * with:
 *
 *   const hasPeriod = Boolean(startDate && endDate);
 *
 * Replace:
 *
 *   const period = formatDate_(startDate) + ' — ' + formatDate_(endDate);
 *
 * with:
 *
 *   const period = hasPeriod
 *     ? formatDate_(startDate) + ' — ' + formatDate_(endDate)
 *     : '';
 *
 * Keep:
 *
 *   pres.replaceAllText('{{ПЕРИОД}}', period);
 *
 * For the no-period certificate the placeholder becomes empty.
 *
 *
 * 2) CALLBACK TO THE WEBSITE AFTER ISSUE/REGENERATION
 *
 * In createCertificate_(), after PDF_URL/QR_URL have been saved to the sheet,
 * add:
 *
 *   const sourceRequestId = String(v[COL.ID - 1] || '').trim();
 *   notifySiteCertificateIssued_(
 *     sourceRequestId,
 *     regNumber,
 *     pdfFile.getUrl(),
 *     verifyUrl
 *   );
 *
 *
 * 3) EMAIL WITHOUT AN EMPTY "TRAINING PERIOD" LINE
 *
 * In sendCertificateEmail_() create:
 *
 *   const periodHtml = period
 *     ? (isEn
 *         ? '<b>Training period:</b> ' + esc_(period) + '<br>'
 *         : '<b>Период обучения:</b> ' + esc_(period) + '<br>')
 *     : '';
 *
 * Then use periodHtml in the HTML instead of the unconditional period line.
 *
 *
 * 4) PUBLIC VERIFICATION PAGE WITHOUT AN EMPTY PERIOD
 *
 * In doGet(), create:
 *
 *   const hasPeriod = Boolean(
 *     row[COL.START_DATE - 1] && row[COL.END_DATE - 1]
 *   );
 *
 * and render the period paragraph only when hasPeriod is true.
 *
 * These four changes preserve the existing manual approval, numbering,
 * PDF generation, QR verification and first-email-only behaviour.
 */
