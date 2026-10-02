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
 * REQUIRED CHANGE inside createCertificate_()
 *
 * Replace the current unconditional period validation:
 *
 *   if (!startDate || !endDate) {
 *     throw new Error('Перед выдачей заполните ...');
 *   }
 *
 * with:
 *
 *   const hasPeriod = Boolean(startDate && endDate);
 *
 * Then replace:
 *
 *   const period = formatDate_(startDate) + ' — ' + formatDate_(endDate);
 *
 * with:
 *
 *   const period = hasPeriod
 *     ? formatDate_(startDate) + ' — ' + formatDate_(endDate)
 *     : '';
 *
 * Existing line:
 *
 *   pres.replaceAllText('{{ПЕРИОД}}', period);
 *
 * can stay unchanged. For a certificate without a period, the placeholder
 * becomes an empty string.
 *
 * This preserves the existing manual approval, numbering, PDF, QR and email
 * workflow while allowing website listeners to request a certificate without
 * a training-period line.
 */
