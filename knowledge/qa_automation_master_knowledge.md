# QA Automation Master Knowledge  
פלטפורמת בדיקות אוטומציה – Backend + UI + Devices + Scenarios

גרסה: v1 (Macro-Level)  
תיאור: מסמך ידע מרכזי עבור כל הבדיקות האוטומטיות בפרויקט (כולל QuickSet היום, ועוד תסריטים/דומיינים בעתיד).

---

## 1. סקירה כללית – מהי הפלטפורמה?

הפלטפורמה היא מערכת בדיקות אוטומטיות רב-שכבתית, שנועדה לתמוך:

- בכמה דומיינים של בדיקות:
  - בדיקות QuickSet (סנכרון שלט/טלוויזיה, Pair/Unpair וכו’)
  - בדיקות אפליקציות (FW / TV Apps / Partner Apps)
  - בדיקות אינטגרציה (Backend APIs, עיבוד לוגים, VolumeProbe וכו’)
- בכמה טסטרים במקביל.
- בכמה מכשירים (STB / TV / דבייסים נוספים) במקביל.

המערכת בנויה לפחות משני רכיבים עיקריים:

1. **Backend – שירות בדיקות (FastAPI / Python)**  
   - מריץ תסריטים מול דבייסים (ADB או פרוטוקולים אחרים).  
   - מנהל Sessions, Steps, Logs ו-Results.  
   - מספק REST API ל־UI, ל־CI, ולכלי אוטומציה נוספים.

2. **Frontend – UI ל-QA Automation (React + Vite + Tailwind)**  
   - מאפשר לטסטר לבחור תסריט, להזין פרמטרים (IP, דומיין, סוג תרחיש).  
   - להפעיל בדיקה בלחיצה.  
   - לראות Steps, סטטוסים, Logs, Metadata ו-Timeline.  
   - לצפות בהיסטוריית סשנים, פילטרים, ו-Dashboard כללי.

הפלטפורמה מיועדת להיות:
- יציבה
- ניתנת להרחבה (scalable)
- מתאימה להוספת דומיינים ותרחישים חדשים בלי שבירה של המערכת הקיימת.

---

## 2. מודל תסריט בדיקה (Test Scenario Model)

כל תסריט בדיקה – ללא קשר לדומיין – צריך להיות מוגדר במבנה אחיד:

### 2.1 מבנה לוגי של תסריט

- **scenario_id** – מזהה קבוע (למשל: `TV_AUTO_SYNC`, `REMOTE_PAIR_UNPAIR`, `APP_LAUNCH_PERF`).  
- **domain** – דומיין לוגי (QuickSet / App / Infra / VolumeProbe / וכו’).  
- **description** – תיאור קצר וברור.  
- **preconditions** – תנאים מקדימים (מצב דבייס, חיבורי רשת, Authorization וכו’).  
- **steps** – רשימת צעדים מוגדרת.  
- **expected_outcomes** – מה נחשב הצלחה.  
- **postconditions** – פעולות ניקוי / Restore state.

### 2.2 מבנה Step

כל step בתסריט אמור להיות אטומי, עקבי, ומתועד:

- `step_id` – שם קצר ויציב (לוגי לקוד ול-UI).  
- `description` – מה step עושה.  
- `status` – אחד מ: `pending`, `running`, `pass`, `fail`, `info`.  
- `timestamp` – זמן ביצוע.  
- `metadata` – שדות חופשיים (נתוני דבייס, לוגים, מדידות).

---

## 3. Backend – ארכיטקטורת שירות הבדיקות

### 3.1 עקרונות

- **API יציב** – כל שינוי חייב לשמור על contract ברור ל-UI ולכלים חיצוניים.  
- **Logging מובנה** – כל Step, כל פעולה על דבייס, כל Exception.  
- **Multi-tester & Multi-device** – אין מצב שסשן של טסטר אחד שובר סשן של אחר.  
- **Separations of Concerns** –  
  - שכבת תקשורת דבייסים (ADB / WebSocket / HTTP)  
  - שכבת לוגיקה של סצנריו  
  - שכבת Persistence (סשנים, תוצאות, לוגים)

### 3.2 Endpoints ליבה (גנרי)

דוגמה לקבוצת endpoints גנרית:

```text
GET  /health
POST /infra/checks
POST /session/start
POST /session/step
POST /session/finish
GET  /session/{session_id}
GET  /session/{session_id}/logs
POST /scenarios/run

3.3 מודל Session גנרי
{
  "session_id": "SESSION_123456",
  "tester_id": "tester-x",
  "domain": "quickset",
  "scenario_id": "TV_AUTO_SYNC",
  "device_ip": "192.168.1.xxx",
  "start_time": "...",
  "end_time": "...",
  "steps": [
    {
      "step": "navigate_home",
      "status": "pass",
      "timestamp": "...",
      "metadata": {}
    }
  ],
  "result": "pass",
  "logs": {
    "device_log": "...",
    "system_log": "..."
  }
}


החלטה: המודל הזה הוא בסיס לכל הדומיינים, לא רק ל-QuickSet.
כל דומיין מוסיף מטא-דאטה ייעודית בתוך metadata או תת-אובייקטים.

4. שכבת דבייסים (Device / ADB / Others)

שכבה זו אחראית על תקשורת בפועל מול דבייסים:

ADB (לממירי Android / STB).

APIs ייעודיים לטלוויזיות / אפליקציות.

כלי Measurement כמו VolumeProbe / אנלייזרים אחרים.

עקרונות:

מבודדת מהלוגיקה של הסצנריו (services).

מדווחת החוצה Exceptions ברורים.

מתעדת כל פקודה / תשובה (Structured Logs).

תומכת ב־retry חכם, במיוחד בבעיות סביבתיות (רשת / זמניות).

5. Frontend – UI ל-QA Automation
5.1 מבנה גנרי
src/
  api/
  components/
  hooks/
  pages/
  types/
  utils/

5.2 עמודים ליבה

Dashboard

סטטוס מערכת

רשימת סשנים פעילים ושהסתיימו

פילטרים (tester_id, domain, scenario_id, result, device_ip)

Session View

רשימת Steps

סטטוסים צבעוניים (pass/fail/info/running)

תצוגת Logs

Metadata / Device Info

כפתור “Run again with same settings”.

Run Scenario Modal

domain (QuickSet / App / Infra / etc)

scenario_id

device_ip או מזהה אחר

tester_id

פרמטרים נוספים לפי הדומיין.

5.3 UX עקרוני

כפתור אחד להרצה עבור כל תסריט.

מודל סטטוסים אחיד לכולם.

UI שלא נשבר כשמוסיפים עוד תסריטים.

Log viewer בצד, לא חוסם את התוך כדי עבודה.

אין תלות בידע פנימי של הטסטר – המידע חי ב-UI.

6. Multi-Tester & Multi-Device

עקרונות:

כל בקשה מה-Backend תזדהה ע"י tester_id ו/או X-Api-Key.

session_id תמיד ייחודי ונשמר עם tester_id ו-device_ip.

אין שיתוף mutable state בין Sessions שונים.

אפשר להריץ את אותו תסריט על כמה דבייסים במקביל בלי התנגשויות.

דגש חשוב:
להתייחס לכל תסריט כאילו הוא רץ בעולם נפרד –
ה-Backend וה-UI רק מציגים/אוספים, לא “מניחים” הנחות.

7. Failure Taxonomy – ברמת מאקרו (לכל הדומיינים)

אחת מאבני הבסיס של הפלטפורמה היא טקסונומיית כשלונות אחידה.
היא חייבת לעבוד גם עבור QuickSet, גם עבור אפליקציות, גם עבור בדיקות אינטגרציה עתידיות.

7.1 קטגוריות על

Functional Failures – הפיצ’ר לא עושה מה שהוא אמור.

Integration Failures – רכיבים/שירותים לא מדברים אחד עם השני נכון.

Environment Failures – סביבה/רשת/OS שוברות את הריצה.

Data Failures – קלט/פלט/DTO לא תקינים.

Test Logic Failures – הטסט עצמו שגוי/חלש.

Tooling/Framework Failures – הכלים עצמם (adb, uvicorn, jest, playwright, וכו’) נופלים.

Timing & Performance Failures – הכול עובד, אבל לא בזמן/קצב הנכון.

UX/Presentation Failures – המידע מוצג לא נכון, למרות שהלוגיקה עובדת.

Device-Level Failures – דבייס פיזי מתנהג לא כמצופה (STB / TV / Phone).

Operational Failures – תקלות תהליך (CI/CD, גרסאות, setup טסטרים).

7.2 טבלת מיפוי כללית
Category	מה זה אומר בפועל	איפה מחפשים קודם
Functional	פיצ’ר לא עובד	קוד לוגיקה / Business Layer
Integration	שירותים לא מסונכרנים	API Contracts / פורמטים
Environment	הכל נופל “מסביב”	רשת / OS / הרשאות
Data	ערכים חסרים / מוזרים	JSON / DB / DTO
Test Logic	הטסט נופל בלי סיבה טובה	Assertions / תזמונים
Tooling	כלי לא מתנהג כמצופה	adb / uvicorn / runners
Timing/Performance	איטי מדי / מגיב באיחור	Latency / Blocking calls
UX	UI מטעה / שבור	React / CSS / Mapping
Device	התנהגות דבייס לא נורמלית	Firmware / HW / Settings
Operational	תהליך עבודה/CI שבור	Pipelines / Versioning
8. Failure Taxonomy – דוגמאות (עם QuickSet אבל לא רק)

הדוגמאות כאן הן אילוסטרציה – המחלקות עצמן תקפות לכל דומיין.

8.1 Functional Example

Scenario: APP_LAUNCH_PERF
-בעיה: האפליקציה לא עולה בכלל.
→ Functional Failure.

8.2 Integration Example

Backend מחזיר שדה manufacturer_name, ה-UI מחפש manufacturer.
→ Integration Failure (contract mismatch).

8.3 Environment Example

בדיקה נופלת רק אצל טסטר על Wi-Fi מסוים.
→ Environment.

8.4 Data Example

response מחזיר null במקום מספר ווליום.
→ Data Failure.

8.5 Test Logic Example

טסט מניח שאירוע יקרה תוך 2 שניות, בפועל מגיע אחרי 5.
→ Test Logic (timeout לא נכון).

וכך הלאה.

9. Template ל-Scenario חדש (באיזה דומיין שלא יהיה)
# <SCENARIO_ID> – <Short Name>

**Domain:** <quickset / app / infra / volumeprobe / ...>  
**Owner:** <team / person>  

## 1. Description
תיאור קצר וברור של מה התסריט בודק.

## 2. Preconditions
- מצב מערכת
- חיבורי רשת
- מצב דבייס
- הרשאות / API Key

## 3. Steps
1. ...
2. ...
3. ...

כל Step צריך להשתקף ב-Backend (Step ID) וב-UI.

## 4. Expected Outcomes
- קריטריוני Pass ברורים.
- מה נחשב Fail.
- מה נחשב Warning / Info בלבד.

## 5. Logging
- מה חובה לתעד (device logs / app logs / metrics).
- איך ניגשים ללוגים.

## 6. Failure Mapping
לכל כישלון – לשייך קטגוריה מתוך Failure Taxonomy (Functional / Integration / וכו’).

10. תבנית לדוח תקלה (Failure Report Template)
## Failure Report

**Category:** (Functional / Integration / Environment / Data / Test Logic / Tooling / Timing / UX / Device / Operational)  
**Domain:** (quickset / app / infra / ...)  
**Scenario ID:**  
**Session ID:**  
**Tester ID:**  
**Device ID/IP:**  

### 1. Description
מה קרה בפועל?

### 2. Expected
מה היה אמור לקרות?

### 3. Evidence
- Backend logs
- Device logs (ADB / system)
- UI screenshots
- Metrics (אם רלוונטי)

### 4. Root Cause Analysis
1. סיווג קטגוריית כשל (ע"פ הטקסונומיה)
2. ממצאים טכניים
3. ניתוח תלות (Device / Network / Version)
4. מסקנה סופית

### 5. Fix Recommendation
פתרון יציב, שלא שובר תסריטים אחרים.

### 6. Regression Notes
מה צריך לבדוק אחרי תיקון?  
אילו תסריטים נוספים ייתכן שנפגעו?

11. כללים למודל GPT ולמפתחים

לא להחזיר קטעי קוד חלקיים – תמיד יחידה מלאה (קובץ / בלוק שלם).

לשמור על עקביות שמות – בין Backend, UI, לוגים וידע.

להשתמש ב-Failure Taxonomy בכל ניתוח תקלה.

לחשוב מאקרו – כל פתרון צריך להתאים גם לדומיינים עתידיים, לא רק ל-QuickSet.

להציע חיזוק יציבות (hardening) כשזה מונע בעיות עתידיות (retry, timeout, logging, validation).

לא לדרוש מהטסטר “להרכיב” חלקים – תמיד להחזיר פתרון שלם וברור.

