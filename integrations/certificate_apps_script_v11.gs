// SkillsSpire certificate automation v11 — website API + optional period + callback
const SPREADSHEET_ID = '1dgUKh_DHzcHEvPg5Dyd9zFPFfY_mRB5VMNU0zcBVU8A';
const SHEET_NAME = 'Реестр';
const SETTINGS_SHEET = 'Настройки';
const TZ = 'Asia/Almaty';

const COL = {
  ID: 1, REQUEST_DATE: 2, SURNAME: 3, NAME: 4, PATRONYMIC: 5,
  FULLNAME: 6, EMAIL: 7, COURSE: 8, HOURS: 9, START_DATE: 10,
  END_DATE: 11, REQUEST_STATUS: 12, APPROVED: 13, REG_NUMBER: 14,
  ISSUE_DATE: 15, CERT_STATUS: 16, QR_URL: 17, PDF_URL: 18,
  PDF_CREATED: 19, EMAIL_SENT: 20, LANGUAGE: 21,
  SOURCE: 22, LOCAL_REQUEST_ID: 23, CALLBACK_URL: 24,
  PERIOD_MODE: 25, CALLBACK_SENT: 26
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Skillsspire')
    .addItem('Выдать сертификат', 'issueCertificate')
    .addItem('Перегенерировать выбранный сертификат', 'regenerateCertificate')
    .addItem('Отправить сертификат на email повторно', 'resendCertificateEmail')
    .addSeparator()
    .addItem('Удалить старую форму и создать новую', 'recreateClientForm')
    .addItem('Проверить систему', 'checkSystem')
    .addToUi();
}

/**
 * Клиент заполняет только:
 * - Язык сертификата: Русский / English
 * - Фамилия
 * - Имя
 * - Email
 * - Название / тема курса
 *
 * Количество часов в форме НЕ спрашивается: по умолчанию 72.
 * Период обучения вводит администратор.
 * Дата выдачи = дата генерации сертификата.
 */
function recreateClientForm() {
  const settings = getSettings_();
  const oldFormId = String(settings['Форма — ID'] || '').trim();

  // Сначала создаём новую форму. Старую удаляем только после успешного создания новой.
  const form = FormApp.create('Заявка на сертификат / Certificate Request — Skillsspire');

  form.setCollectEmail(false);
  form.setTitle('Заявка на сертификат / Certificate Request — Skillsspire');
  form.setDescription(
    'RU: Выберите язык сертификата. Фамилию, имя и название курса вводите именно так, ' +
    'как они должны выглядеть в сертификате. Для сертификата на английском введите эти данные на английском. ' +
    'Количество часов указывать не нужно: автоматически ставится 72 академических часа.\n\n' +
    'EN: Choose the certificate language. Enter your surname, first name, and course title exactly as they should appear on the certificate. ' +
    'For an English certificate, enter these details in English. You do not need to enter the number of hours: 72 academic hours are added automatically.'
  );
  form.setConfirmationMessage(
    'RU: Заявка получена. После проверки сертификат будет автоматически отправлен на указанный email.\n' +
    'EN: Your request has been received. After verification, the certificate will be sent automatically to the email address provided.'
  );

  form.addMultipleChoiceItem()
    .setTitle('Язык сертификата / Certificate language')
    .setChoiceValues(['Русский', 'English'])
    .setRequired(true);

  form.addTextItem()
    .setTitle('Фамилия / Surname')
    .setHelpText('RU: Введите так, как должно быть указано в сертификате. / EN: Enter exactly as it should appear on the certificate.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Имя / First name')
    .setHelpText('RU: Введите так, как должно быть указано в сертификате. / EN: Enter exactly as it should appear on the certificate.')
    .setRequired(true);

  const emailValidation = FormApp.createTextValidation()
    .requireTextIsEmail()
    .setHelpText('RU: Введите действующий email. / EN: Enter a valid email address.')
    .build();

  form.addTextItem()
    .setTitle('Email')
    .setValidation(emailValidation)
    .setRequired(true);

  form.addTextItem()
    .setTitle('Название курса / Course title')
    .setHelpText('RU: Для English введите название курса на английском. / EN: For an English certificate, enter the course title in English.')
    .setRequired(true);

  // Публикуем и разрешаем ответы.
  try { form.setPublished(true); } catch (e) {}
  try { form.setAcceptingResponses(true); } catch (e) {}

  // Один актуальный триггер на новую форму.
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'onClientFormSubmit')
    .forEach(t => ScriptApp.deleteTrigger(t));

  ScriptApp.newTrigger('onClientFormSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();

  // Записываем новую форму в настройки до удаления старой.
  setSetting_('Форма — ID', form.getId());
  setSetting_('Форма — URL', form.getPublishedUrl());
  setSetting_('Поля формы клиента',
    'Язык; Фамилия/Surname; Имя/First name; Email; Название курса/Course title'
  );

  // Старую форму удаляем только после того, как новая полностью создана и подключена.
  if (oldFormId && oldFormId !== form.getId()) {
    try {
      DriveApp.getFileById(oldFormId).setTrashed(true);
    } catch (e) {
      console.warn('Старую форму не удалось переместить в корзину: ' + e.message);
    }
  }

  SpreadsheetApp.getUi().alert(
    'Новая форма создана',
    'Старая форма удалена после успешного создания новой.\n\n' +
    'В новой форме ровно 5 полей:\n' +
    '• Язык сертификата / Certificate language\n' +
    '• Фамилия / Surname\n' +
    '• Имя / First name\n' +
    '• Email\n' +
    '• Название курса / Course title\n\n' +
    'Количество часов слушатель НЕ вводит. Автоматически: 72.\n\n' +
    'Ссылка для слушателей:\n' + form.getPublishedUrl(),
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}
function onClientFormSubmit(e) {
  const answers = {};
  e.response.getItemResponses().forEach(ir => {
    answers[String(ir.getItem().getTitle()).trim()] = ir.getResponse();
  });

  const language = normalizeLanguage_(
    answers['Язык сертификата / Certificate language'] || 'Русский'
  );
  const surname = String(answers['Фамилия / Surname'] || '').trim();
  const name = String(answers['Имя / First name'] || '').trim();
  const email = String(answers['Email'] || '').trim();
  const course = String(answers['Название курса / Course title'] || '').trim();

  const settings = getSettings_();
  const defaultHours = Number(settings['Количество часов по умолчанию'] || 72);
  const fullName = [surname, name].filter(Boolean).join(' ').trim();
  const now = new Date();
  const requestId =
    'REQ-' + Utilities.formatDate(now, TZ, 'yyyyMMdd-HHmmss') +
    '-' + Math.floor(100 + Math.random() * 900);

  const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);

  sh.appendRow([
    requestId, now, surname, name, '', fullName, email, course, defaultHours,
    '', '', 'На проверке', false, '', '', '', '', '', '', false, language
  ]);
}

function issueCertificate() { runCertificateAction_(false); }
function regenerateCertificate() { runCertificateAction_(true); }

function runCertificateAction_(isRegenerate) {
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error('Система уже обрабатывает сертификат. Подождите несколько секунд и повторите.');
  }
  try {
    createCertificate_(isRegenerate);
  } finally {
    lock.releaseLock();
  }
}

function createCertificate_(isRegenerate, rowOverride) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sh = ss.getSheetByName(SHEET_NAME);
  const row = rowOverride || SpreadsheetApp.getActiveRange().getRow();

  if (row < 2) throw new Error('Выберите строку участника в листе «Реестр».');

  const v = sh.getRange(row, 1, 1, COL.LANGUAGE).getValues()[0];

  if (v[COL.APPROVED - 1] !== true) {
    throw new Error('Сначала проверьте данные и поставьте галочку «Разрешить выдачу».');
  }

  const settings = getSettings_();
  const language = normalizeLanguage_(v[COL.LANGUAGE - 1] || 'Русский');

  const templateId = language === 'English'
    ? String(settings['Шаблон сертификата EN'] || '').trim()
    : String(settings['Шаблон сертификата RU'] || settings['Шаблон Google Slides'] || '').trim();

  const outputFolderId = String(settings['Папка PDF 2026'] || '').trim();
  const verifyBaseUrl = String(settings['URL проверки'] || '').trim();

  if (!templateId || !outputFolderId) {
    throw new Error('В листе «Настройки» не заполнен шаблон для выбранного языка или папка PDF.');
  }

  // ФИО берём из текущих значений Фамилия + Имя, чтобы ваши исправления
  // в Реестре перед выдачей всегда попадали в сертификат.
  const fullName =
    [v[COL.SURNAME - 1], v[COL.NAME - 1]]
      .map(x => String(x || '').trim())
      .filter(Boolean)
      .join(' ')
      .trim();

  const email = String(v[COL.EMAIL - 1] || '').trim();
  const course = String(v[COL.COURSE - 1] || '').trim();

  let hours = Number(v[COL.HOURS - 1]);
  if (!hours) {
    hours = Number(settings['Количество часов по умолчанию'] || 72);
    sh.getRange(row, COL.HOURS).setValue(hours);
  }

  const startDate = v[COL.START_DATE - 1];
  const endDate = v[COL.END_DATE - 1];
  const periodMode = normalizePeriodMode_(v[COL.PERIOD_MODE - 1], startDate, endDate);
  const includePeriod = periodMode === 'with_period';

  if (!fullName || !course) throw new Error('Проверьте фамилию, имя и название курса.');
  if (!email) throw new Error('В строке нет email слушателя.');
  if (includePeriod && (!startDate || !endDate)) {
    throw new Error('Для сертификата с периодом заполните «Дата начала» и «Дата окончания».');
  }

  let regNumber = String(v[COL.REG_NUMBER - 1] || '').trim();
  let nextNumber = Number(settings['Следующий номер']);

  if (isRegenerate) {
    if (!regNumber) throw new Error('Для перегенерации у сертификата уже должен быть номер.');
  } else {
    if (regNumber) {
      throw new Error('У строки уже есть номер. Используйте «Перегенерировать выбранный сертификат».');
    }
    if (!nextNumber) throw new Error('В настройках не указан следующий номер.');

    const prefix = String(settings['Префикс'] || 'SS-2026-');
    regNumber = prefix + String(nextNumber).padStart(5, '0');
  }

  // При обычной выдаче дата выдачи = текущая дата.
  // При перегенерации сохраняем первоначальную дату выдачи, чтобы исправление макета
  // не меняло юридически значимую дату сертификата.
  const issueDate = (isRegenerate && v[COL.ISSUE_DATE - 1])
    ? new Date(v[COL.ISSUE_DATE - 1])
    : new Date();
  const period = includePeriod
    ? formatDate_(startDate) + ' — ' + formatDate_(endDate)
    : '';
  const issueDateText = formatDate_(issueDate);
  const yearText = Utilities.formatDate(issueDate, TZ, 'yyyy');

  const verifyUrl = verifyBaseUrl
    ? verifyBaseUrl + '?id=' + encodeURIComponent(regNumber)
    : '';

  const folder = DriveApp.getFolderById(outputFolderId);

  if (isRegenerate) {
    const oldId = extractDriveId_(String(v[COL.PDF_URL - 1] || ''));
    if (oldId) {
      try { DriveApp.getFileById(oldId).setTrashed(true); } catch (e) {}
    }
  }

  const tempPrefix = language === 'English' ? 'TEMP Certificate ' : 'TEMP Сертификат ';
  const tempFile = DriveApp.getFileById(templateId)
    .makeCopy(tempPrefix + regNumber + ' — ' + fullName, folder);

  const pres = SlidesApp.openById(tempFile.getId());
  const slide = pres.getSlides()[0];

  // Название курса адаптируется автоматически:
  // короткое остаётся крупным в одну строку, длинное делится максимум на две строки,
  // а размер шрифта уменьшается только настолько, насколько нужно для макета.
  const courseLayout = prepareCourseLayout_(slide, course);

  pres.replaceAllText('{{ФИО}}', fullName);
  pres.replaceAllText('{{КУРС}}', courseLayout.text);
  pres.replaceAllText('{{ЧАСЫ}}', String(hours));
  if (includePeriod) {
    pres.replaceAllText('{{ПЕРИОД}}', period);
  } else {
    removeTrainingPeriodElements_(slide);
    pres.replaceAllText('{{ПЕРИОД}}', '');
  }
  pres.replaceAllText('{{НОМЕР}}', regNumber);
  pres.replaceAllText('{{ДАТА_ВЫДАЧИ}}', issueDateText);
  pres.replaceAllText('{{ГОД}}', yearText);
  pres.replaceAllText('{{QR}}', '');
  if (verifyUrl) {
    const qrApi =
      'https://api.qrserver.com/v1/create-qr-code/?size=350x350&data=' +
      encodeURIComponent(verifyUrl);
    const qrBlob = UrlFetchApp.fetch(qrApi).getBlob().setName('qr.png');
    const qrImage = slide.insertImage(qrBlob, 608, 382, 64, 64);
    // QR remains scannable, and tapping/clicking the QR in the PDF opens verification.
    qrImage.setLinkUrl(verifyUrl);
    qrImage.setTitle('Verify certificate');
    qrImage.setDescription(verifyUrl);
  }

  pres.saveAndClose();

  const pdfName = language === 'English'
    ? 'Certificate ' + regNumber + ' — ' + fullName + '.pdf'
    : 'Сертификат ' + regNumber + ' — ' + fullName + '.pdf';

  const pdfBlob = DriveApp.getFileById(tempFile.getId())
    .getAs(MimeType.PDF)
    .setName(pdfName);
  const pdfFile = folder.createFile(pdfBlob);

  try {
    pdfFile.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  } catch (e) {}

  tempFile.setTrashed(true);

  sh.getRange(row, COL.FULLNAME).setValue(fullName);
  sh.getRange(row, COL.REG_NUMBER).setValue(regNumber);
  sh.getRange(row, COL.ISSUE_DATE).setValue(issueDate);
  sh.getRange(row, COL.CERT_STATUS).setValue('Действителен');
  sh.getRange(row, COL.QR_URL).setValue(verifyUrl);
  sh.getRange(row, COL.PDF_URL).setValue(pdfFile.getUrl());
  sh.getRange(row, COL.PDF_CREATED).setValue(new Date());
  sh.getRange(row, COL.REQUEST_STATUS).setValue('Выдан');
  sh.getRange(row, COL.LANGUAGE).setValue(language);
  sh.getRange(row, COL.PERIOD_MODE).setValue(periodMode);

  if (!isRegenerate) setSetting_('Следующий номер', nextNumber + 1);

  let sent = v[COL.EMAIL_SENT - 1] === true;

  // Автоматическое письмо отправляем ТОЛЬКО при первой выдаче.
  // Перегенерация нужна для исправления макета/данных и не должна создавать дубликаты писем.
  if (!isRegenerate) {
    sent = sendCertificateEmail_(
      language, email, fullName, course, hours, period,
      regNumber, issueDateText, pdfFile.getUrl(), verifyUrl, pdfBlob
    );
    sh.getRange(row, COL.EMAIL_SENT).setValue(sent);
  }

  if (!isRegenerate) {
    callbackCertificateSite_(sh, row, {
      status: 'issued',
      certificate_number: regNumber,
      pdf_url: pdfFile.getUrl(),
      verify_url: verifyUrl
    });
  }

  const message = isRegenerate
    ? 'Сертификат ' + regNumber + ' перегенерирован (' + language + ').\n' +
      'Письмо повторно НЕ отправлялось. При необходимости используйте отдельную команду меню «Отправить сертификат на email повторно».'
    : 'Сертификат ' + regNumber + ' создан (' + language + ').\n' +
      (sent ? 'Письмо отправлено на ' + email : 'PDF создан, но письмо не удалось отправить.');

  SpreadsheetApp.getUi().alert(
    'Готово',
    message + '\n\n' + pdfFile.getUrl(),
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}


/**
 * Возвращает название курса, подготовленное для сертификата, и настраивает
 * текстовый блок {{КУРС}} под одну или две строки.
 */
function prepareCourseLayout_(slide, course) {
  const clean = String(course || '').replace(/\s+/g, ' ').trim();
  const twoLines = clean.length > 48;
  const displayText = twoLines ? splitCourseIntoTwoLines_(clean) : clean;
  const lines = displayText.split('\n');
  const maxLineLength = Math.max.apply(null, lines.map(s => s.length));

  // 20.5 pt — исходный размер в шаблоне.
  // При длинных названиях уменьшаем размер пропорционально длине самой длинной строки.
  let fontSize = Math.min(20.5, 20.5 * 43 / Math.max(43, maxLineLength));
  fontSize = Math.max(11.5, Math.round(fontSize * 2) / 2);

  const elements = slide.getPageElements();
  let courseShape = null;
  let hoursShape = null;

  elements.forEach(el => {
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) return;
    const shape = el.asShape();
    const txt = shape.getText().asString();
    if (txt.indexOf('{{КУРС}}') !== -1) courseShape = shape;
    if (txt.indexOf('{{ЧАСЫ}}') !== -1) hoursShape = shape;
  });

  if (courseShape) {
    courseShape.setTop(278);
    courseShape.setHeight(twoLines ? 50 : 34);
    courseShape.getText().getTextStyle().setFontSize(fontSize);
    try { courseShape.getText().getParagraphStyle().setLineSpacing(92); } catch (e) {}
  }

  // Освобождаем место под вторую строку курса и не допускаем наложения на часы.
  if (hoursShape) {
    hoursShape.setTop(twoLines ? 335 : 318);
  }

  return { text: displayText, fontSize: fontSize, lines: lines.length };
}

/**
 * Делит название курса в ближайшем к середине пробеле, чтобы две строки
 * были максимально равными по длине.
 */
function splitCourseIntoTwoLines_(text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return text;

  let bestIndex = 1;
  let bestScore = Number.POSITIVE_INFINITY;

  for (let i = 1; i < words.length; i++) {
    const left = words.slice(0, i).join(' ');
    const right = words.slice(i).join(' ');
    const score = Math.max(left.length, right.length) + Math.abs(left.length - right.length) * 0.2;
    if (score < bestScore) {
      bestScore = score;
      bestIndex = i;
    }
  }

  return words.slice(0, bestIndex).join(' ') + '\n' + words.slice(bestIndex).join(' ');
}

/**
 * Явная повторная отправка. Нужна только если администратор действительно
 * хочет ещё раз отправить уже созданный сертификат.
 */
function resendCertificateEmail() {
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error('Система уже выполняет другую операцию. Подождите несколько секунд.');
  }

  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sh = ss.getSheetByName(SHEET_NAME);
    const row = SpreadsheetApp.getActiveRange().getRow();
    if (row < 2) throw new Error('Выберите строку участника в листе «Реестр».');

    const v = sh.getRange(row, 1, 1, COL.LANGUAGE).getValues()[0];
    const regNumber = String(v[COL.REG_NUMBER - 1] || '').trim();
    const pdfUrl = String(v[COL.PDF_URL - 1] || '').trim();
    const email = String(v[COL.EMAIL - 1] || '').trim();

    if (!regNumber || !pdfUrl) throw new Error('Сначала создайте сертификат.');
    if (!email) throw new Error('В строке нет email слушателя.');

    const ui = SpreadsheetApp.getUi();
    const confirm = ui.alert(
      'Повторная отправка',
      'Отправить сертификат ' + regNumber + ' ещё раз на ' + email + '?',
      ui.ButtonSet.YES_NO
    );
    if (confirm !== ui.Button.YES) return;

    const pdfId = extractDriveId_(pdfUrl);
    if (!pdfId) throw new Error('Не удалось определить файл PDF.');
    const pdfBlob = DriveApp.getFileById(pdfId).getBlob();

    const language = normalizeLanguage_(v[COL.LANGUAGE - 1] || 'Русский');
    const fullName = String(v[COL.FULLNAME - 1] || '').trim() ||
      [v[COL.SURNAME - 1], v[COL.NAME - 1]].map(x => String(x || '').trim()).filter(Boolean).join(' ');
    const course = String(v[COL.COURSE - 1] || '').trim();
    const hours = Number(v[COL.HOURS - 1] || 72);
    const period = formatDate_(v[COL.START_DATE - 1]) + ' — ' + formatDate_(v[COL.END_DATE - 1]);
    const issueDateText = formatDate_(v[COL.ISSUE_DATE - 1] || new Date());
    const verifyUrl = String(v[COL.QR_URL - 1] || '').trim();

    const sent = sendCertificateEmail_(
      language, email, fullName, course, hours, period,
      regNumber, issueDateText, pdfUrl, verifyUrl, pdfBlob
    );

    sh.getRange(row, COL.EMAIL_SENT).setValue(sent);

    ui.alert(
      sent ? 'Письмо отправлено' : 'Ошибка отправки',
      sent ? 'Сертификат повторно отправлен на ' + email + '.' : 'Не удалось отправить письмо.',
      ui.ButtonSet.OK
    );
  } finally {
    lock.releaseLock();
  }
}

function sendCertificateEmail_(language, email, fullName, course, hours, period, regNumber, issueDateText, pdfUrl, verifyUrl, pdfBlob) {
  try {
    const isEn = language === 'English';
    const subject = isEn
      ? 'Your Skillsspire certificate is ready'
      : 'Ваш сертификат Skillsspire готов';

    const html = isEn
      ? '<p>Hello, ' + esc_(fullName) + '!</p>' +
        '<p>Your Skillsspire certificate is ready.</p>' +
        '<p><b>Course:</b> “' + esc_(course) + '”<br>' +
        '<b>Academic hours:</b> ' + esc_(hours) + '<br>' +
        (period ? '<b>Training period:</b> ' + esc_(period) + '<br>' : '') +
        '<b>Registration No.:</b> ' + esc_(regNumber) + '<br>' +
        '<b>Date of issue:</b> ' + esc_(issueDateText) + '</p>' +
        '<p><a href="' + esc_(pdfUrl) + '">Open certificate</a></p>' +
        (verifyUrl ? '<p><a href="' + esc_(verifyUrl) + '">Verify certificate</a></p>' : '') +
        '<p>The PDF certificate is also attached to this email.</p>' +
        '<p>Best regards,<br>Skillsspire</p>'
      : '<p>Здравствуйте, ' + esc_(fullName) + '!</p>' +
        '<p>Ваш сертификат Skillsspire готов.</p>' +
        '<p><b>Курс:</b> «' + esc_(course) + '»<br>' +
        '<b>Количество часов:</b> ' + esc_(hours) + '<br>' +
        (period ? '<b>Период обучения:</b> ' + esc_(period) + '<br>' : '') +
        '<b>Регистрационный №:</b> ' + esc_(regNumber) + '<br>' +
        '<b>Дата выдачи:</b> ' + esc_(issueDateText) + '</p>' +
        '<p><a href="' + esc_(pdfUrl) + '">Открыть сертификат</a></p>' +
        (verifyUrl ? '<p><a href="' + esc_(verifyUrl) + '">Проверить подлинность сертификата</a></p>' : '') +
        '<p>PDF-файл сертификата также прикреплён к этому письму.</p>' +
        '<p>С уважением,<br>Skillsspire</p>';

    const body = isEn
      ? 'Your Skillsspire certificate is ready.\nRegistration No.: ' + regNumber +
        '\nOpen certificate: ' + pdfUrl +
        (verifyUrl ? '\nVerify certificate: ' + verifyUrl : '')
      : 'Ваш сертификат Skillsspire готов.\nРегистрационный №: ' + regNumber +
        '\nОткрыть сертификат: ' + pdfUrl +
        (verifyUrl ? '\nПроверка подлинности: ' + verifyUrl : '');

    MailApp.sendEmail({
      to: email,
      subject: subject,
      htmlBody: html,
      body: body,
      attachments: [pdfBlob]
    });
    return true;
  } catch (e) {
    console.error(e);
    return false;
  }
}

function doPost(e) {
  try {
    const data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (String(data.source || '') !== 'skillsspire_site') {
      return jsonResponse_({ok:false, error:'Unsupported source'});
    }

    const settings = getSettings_();
    const expectedToken = String(settings['Website API token'] || '').trim();
    const receivedToken = String(data.token || '').trim();
    if (!expectedToken || receivedToken !== expectedToken) {
      return jsonResponse_({ok:false, error:'Unauthorized'});
    }

    const surname = String(data.surname || '').trim();
    const name = String(data.name || '').trim();
    const fullName = String(data.full_name || [surname, name].filter(Boolean).join(' ')).trim();
    const email = String(data.email || '').trim();
    const course = String(data.course || '').trim();
    const hours = Number(data.hours || settings['Количество часов по умолчанию'] || 72);
    const language = normalizeLanguage_(data.language || 'Русский');
    const periodMode = normalizePeriodMode_(data.period_mode, data.start_date, data.end_date);
    const localRequestId = String(data.local_request_id || '').trim();
    const callbackUrl = String(data.callback_url || '').trim();

    if (!fullName || !email || !course || !localRequestId) {
      return jsonResponse_({ok:false, error:'Missing required fields'});
    }

    const startDate = periodMode === 'with_period' ? parseIsoDate_(data.start_date) : '';
    const endDate = periodMode === 'with_period' ? parseIsoDate_(data.end_date) : '';
    if (periodMode === 'with_period' && (!startDate || !endDate)) {
      return jsonResponse_({ok:false, error:'Training period dates are required'});
    }

    const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
    ensureWebsiteColumns_(sh);

    const lastRow = sh.getLastRow();
    if (lastRow >= 2) {
      const existingIds = sh.getRange(2, COL.LOCAL_REQUEST_ID, lastRow - 1, 1).getValues();
      for (let i = 0; i < existingIds.length; i++) {
        if (String(existingIds[i][0] || '').trim() === localRequestId) {
          const existingRow = i + 2;
          return jsonResponse_({
            ok:true,
            request_id:String(sh.getRange(existingRow, COL.ID).getValue() || ''),
            duplicate:true
          });
        }
      }
    }

    const now = new Date();
    const requestId =
      'SITE-' + Utilities.formatDate(now, TZ, 'yyyyMMdd-HHmmss') +
      '-' + Math.floor(100 + Math.random() * 900);

    const manualApproval = String(settings['Ручное подтверждение'] || 'Да').trim().toLowerCase();
    const approved = !['да','yes','true','1'].includes(manualApproval);

    sh.appendRow([
      requestId, now, surname, name, '', fullName, email, course, hours,
      startDate, endDate, 'На проверке', approved, '', '', '', '', '', '', false, language,
      'skillsspire_site', localRequestId, callbackUrl, periodMode, false
    ]);

    return jsonResponse_({ok:true, request_id:requestId});
  } catch (err) {
    console.error(err);
    return jsonResponse_({ok:false, error:String(err && err.message || err)});
  }
}

function doGet(e) {
  const id = String((e && e.parameter && e.parameter.id) || '').trim();

  if (!id) {
    return HtmlService.createHtmlOutput(
      page_('Проверка сертификата / Certificate Verification',
        '<p>Укажите регистрационный номер сертификата.</p>')
    );
  }

  const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
  const lastRow = sh.getLastRow();
  const data = lastRow < 2 ? [] : sh.getRange(2, 1, lastRow - 1, COL.CALLBACK_SENT).getValues();
  const row = data.find(r => String(r[COL.REG_NUMBER - 1] || '').trim() === id);

  if (!row) {
    return HtmlService.createHtmlOutput(
      page_('Сертификат не найден / Certificate Not Found',
        '<p>Регистрационный номер <b>' + esc_(id) + '</b> отсутствует в реестре.</p>')
    );
  }

  const language = normalizeLanguage_(row[COL.LANGUAGE - 1] || 'Русский');
  const isEn = language === 'English';

  if (String(row[COL.CERT_STATUS - 1] || '') === 'Аннулирован') {
    return HtmlService.createHtmlOutput(
      page_(isEn ? 'Certificate Revoked' : 'Сертификат аннулирован',
        isEn
          ? '<p>Certificate <b>' + esc_(id) + '</b> has been revoked.</p>'
          : '<p>Сертификат <b>' + esc_(id) + '</b> имеет статус «Аннулирован».</p>')
    );
  }

  const fullName =
    [row[COL.SURNAME - 1], row[COL.NAME - 1]]
      .map(x => String(x || '').trim())
      .filter(Boolean)
      .join(' ')
      .trim() ||
    String(row[COL.FULLNAME - 1] || '').trim();
  const pdfUrl = String(row[COL.PDF_URL - 1] || '').trim();
  const periodMode = normalizePeriodMode_(row[COL.PERIOD_MODE - 1], row[COL.START_DATE - 1], row[COL.END_DATE - 1]);
  const periodHtmlEn = periodMode === 'with_period'
    ? '<p><b>Training period:</b> ' + esc_(formatDate_(row[COL.START_DATE - 1])) + ' — ' + esc_(formatDate_(row[COL.END_DATE - 1])) + '</p>'
    : '';
  const periodHtmlRu = periodMode === 'with_period'
    ? '<p><b>Период обучения:</b> ' + esc_(formatDate_(row[COL.START_DATE - 1])) + ' — ' + esc_(formatDate_(row[COL.END_DATE - 1])) + '</p>'
    : '';

  const html = isEn
    ? '<div class="ok">✓ Certificate is valid</div>' +
      '<h2>' + esc_(fullName) + '</h2>' +
      '<p><b>Course:</b> “' + esc_(row[COL.COURSE - 1]) + '”</p>' +
      '<p><b>Academic hours:</b> ' + esc_(row[COL.HOURS - 1]) + '</p>' +
      periodHtmlEn +
      '<p><b>Registration No.:</b> ' + esc_(id) + '</p>' +
      '<p><b>Date of issue:</b> ' + esc_(formatDate_(row[COL.ISSUE_DATE - 1])) + '</p>' +
      '<p><b>City:</b> Astana</p>' +
      (pdfUrl ? '<p style="margin-top:26px"><a class="button" target="_top" href="' + esc_(pdfUrl) + '">Open certificate</a></p>' : '')
    : '<div class="ok">✓ Сертификат действителен</div>' +
      '<h2>' + esc_(fullName) + '</h2>' +
      '<p><b>Курс:</b> «' + esc_(row[COL.COURSE - 1]) + '»</p>' +
      '<p><b>Количество часов:</b> ' + esc_(row[COL.HOURS - 1]) + '</p>' +
      periodHtmlRu +
      '<p><b>Регистрационный №:</b> ' + esc_(id) + '</p>' +
      '<p><b>Дата выдачи:</b> ' + esc_(formatDate_(row[COL.ISSUE_DATE - 1])) + '</p>' +
      '<p><b>Город:</b> Астана</p>' +
      (pdfUrl ? '<p style="margin-top:26px"><a class="button" target="_top" href="' + esc_(pdfUrl) + '">Открыть сертификат</a></p>' : '');

  return HtmlService.createHtmlOutput(
    page_(isEn ? 'Certificate Verification' : 'Проверка сертификата', html)
  );
}


function checkSystem() {
  const settings = getSettings_();
  const problems = [];
  const ok = [];

  // 1. Проверка формы
  try {
    const formId = String(settings['Форма — ID'] || '').trim();
    if (!formId) {
      problems.push('Не указан ID Google Form.');
    } else {
      const form = FormApp.openById(formId);
      const titles = form.getItems().map(i => String(i.getTitle() || '').trim());
      const expected = [
        'Язык сертификата / Certificate language',
        'Фамилия / Surname',
        'Имя / First name',
        'Email',
        'Название курса / Course title'
      ];

      if (titles.length !== expected.length) {
        problems.push('В форме должно быть ровно 5 полей, сейчас: ' + titles.length + '.');
      }

      expected.forEach(t => {
        if (!titles.includes(t)) problems.push('В форме отсутствует поле: ' + t);
      });

      const forbidden = titles.filter(t =>
        /количество\s*часов|hours/i.test(t) &&
        t !== 'Название курса / Course title'
      );
      if (forbidden.length) {
        problems.push('В форме найдено лишнее поле с часами: ' + forbidden.join(', '));
      }

      if (titles.length === expected.length &&
          expected.every(t => titles.includes(t)) &&
          forbidden.length === 0) {
        ok.push('Google Form: новая двуязычная форма, 5 правильных полей, поля часов нет.');
      }
    }
  } catch (e) {
    problems.push('Не удалось проверить Google Form: ' + e.message);
  }

  // 2. Проверка настроек
  if (Number(settings['Количество часов по умолчанию']) === 72) {
    ok.push('Количество часов по умолчанию: 72.');
  } else {
    problems.push('Количество часов по умолчанию должно быть 72.');
  }

  if (String(settings['Шаблон сертификата RU'] || '').trim()) {
    ok.push('Русский шаблон указан.');
  } else {
    problems.push('Не указан русский шаблон.');
  }

  if (String(settings['Шаблон сертификата EN'] || '').trim()) {
    ok.push('Английский шаблон указан.');
  } else {
    problems.push('Не указан английский шаблон.');
  }

  if (String(settings['URL проверки'] || '').trim()) {
    ok.push('URL проверки QR указан.');
  } else {
    problems.push('Не указан URL проверки QR.');
  }

  const message =
    (ok.length ? 'OK:\\n• ' + ok.join('\\n• ') + '\\n\\n' : '') +
    (problems.length ? 'НУЖНО ИСПРАВИТЬ:\\n• ' + problems.join('\\n• ') : 'Система настроена корректно.');

  SpreadsheetApp.getUi().alert(
    problems.length ? 'Проверка системы: есть замечания' : 'Проверка системы: всё готово',
    message,
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}


function normalizePeriodMode_(value, startDate, endDate) {
  const s = String(value || '').trim().toLowerCase();
  if (s === 'without_period' || s === 'без периода' || s === 'no_period') return 'without_period';
  if (s === 'with_period' || s === 'с периодом' || s === 'period') return 'with_period';
  return (startDate && endDate) ? 'with_period' : 'without_period';
}

function parseIsoDate_(value) {
  const s = String(value || '').trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return '';
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

function removeTrainingPeriodElements_(slide) {
  slide.getPageElements().slice().reverse().forEach(el => {
    if (el.getPageElementType() !== SlidesApp.PageElementType.SHAPE) return;
    const text = String(el.asShape().getText().asString() || '').trim();
    if (
      text.indexOf('{{ПЕРИОД}}') !== -1 ||
      /^Период обучения:?$/i.test(text) ||
      /^Training period:?$/i.test(text)
    ) {
      el.remove();
    }
  });
}

function ensureWebsiteColumns_(sh) {
  const headers = [
    ['Источник', COL.SOURCE],
    ['Local request ID', COL.LOCAL_REQUEST_ID],
    ['Callback URL', COL.CALLBACK_URL],
    ['Режим периода', COL.PERIOD_MODE],
    ['Callback sent', COL.CALLBACK_SENT]
  ];
  headers.forEach(item => {
    if (!String(sh.getRange(1, item[1]).getValue() || '').trim()) {
      sh.getRange(1, item[1]).setValue(item[0]);
    }
  });
}

function callbackCertificateSite_(sh, row, payload) {
  try {
    const source = String(sh.getRange(row, COL.SOURCE).getValue() || '').trim();
    const localRequestId = String(sh.getRange(row, COL.LOCAL_REQUEST_ID).getValue() || '').trim();
    const callbackUrl = String(sh.getRange(row, COL.CALLBACK_URL).getValue() || '').trim();
    if (source !== 'skillsspire_site' || !localRequestId || !callbackUrl) return;

    const settings = getSettings_();
    const token = String(settings['Website API token'] || '').trim();
    const body = Object.assign({}, payload, {token: token, local_request_id: localRequestId});
    const response = UrlFetchApp.fetch(callbackUrl, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(body),
      muteHttpExceptions: true
    });
    sh.getRange(row, COL.CALLBACK_SENT).setValue(
      response.getResponseCode() >= 200 && response.getResponseCode() < 300
    );
  } catch (err) {
    console.error('Callback failed: ' + err.message);
    try { sh.getRange(row, COL.CALLBACK_SENT).setValue(false); } catch (e) {}
  }
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function normalizeLanguage_(value) {
  const s = String(value || '').trim().toLowerCase();
  return (s === 'english' || s === 'en' || s === 'английский') ? 'English' : 'Русский';
}

function getSettings_() {
  const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SETTINGS_SHEET);
  const values = sh.getRange(2, 1, Math.max(sh.getLastRow() - 1, 1), 2).getValues();
  const out = {};
  values.forEach(r => { if (r[0] !== '') out[String(r[0]).trim()] = r[1]; });
  return out;
}

function setSetting_(key, value) {
  const sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SETTINGS_SHEET);
  const last = sh.getLastRow();
  const values = sh.getRange(2, 1, Math.max(last - 1, 1), 1).getValues();

  for (let i = 0; i < values.length; i++) {
    if (String(values[i][0]).trim() === key) {
      sh.getRange(i + 2, 2).setValue(value);
      return;
    }
  }
  sh.appendRow([key, value]);
}

function formatDate_(value) {
  if (!value) return '';
  const d = value instanceof Date ? value : new Date(value);
  return Utilities.formatDate(d, TZ, 'dd.MM.yyyy');
}

function extractDriveId_(url) {
  if (!url) return '';
  const m = String(url).match(/[-\w]{25,}/);
  return m ? m[0] : '';
}

function esc_(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function page_(title, body) {
  return '<!doctype html><html><head><meta charset="utf-8"><base target="_top">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>' + esc_(title) + '</title>' +
    '<style>body{font-family:Arial,sans-serif;background:#f6f9fe;margin:0;padding:28px;color:#172033}' +
    '.card{max-width:680px;margin:32px auto;background:#fff;border:1px solid #dbe6f8;border-radius:18px;padding:34px;box-shadow:0 12px 38px rgba(19,60,130,.08)}' +
    'h1{color:#1041aa;font-size:27px;margin:0 0 24px}.ok{color:#168147;font-weight:700;margin-bottom:18px}' +
    'h2{font-size:26px;margin:0 0 26px}p{line-height:1.65;margin:10px 0}' +
    '.button{display:inline-block;background:#1041aa;color:white;text-decoration:none;padding:12px 18px;border-radius:9px}' +
    '</style></head><body><div class="card"><h1>' + esc_(title) + '</h1>' + body + '</div></body></html>';
}
