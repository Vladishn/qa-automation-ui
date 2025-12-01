# QuickSet QA Automation — Knowledge Base
גרסה: v1
תיאור: מסמך ידע מרכזי עבור פרויקט בדיקות האוטומציה ל-QuickSet, כולל UI, FastAPI, ADB, תסריטי בדיקה ותחקורים.

---

## 1. סקירה כללית

פרויקט *QuickSet QA Automation* הוא מערכת בדיקות אוטומציה לממירי SEI X4 (Technicolor S70PCI).
המערכת בנויה משני רבדים עיקריים:

1. **Backend – FastAPI**
   מנוע אוטומציה שמריץ תסריטים אמיתיים מול הממיר:
   - ADB connect / reconnect
   - הפעלת תרחישים (TV_AUTO_SYNC, Remote Pair/Unpair ועוד)
   - איסוף לוגים (logcat + פעולות ADB)
   - תיעוד JSONL מובנה לכל Step
   - תמיכה ב-multi-tester עם API Keys

2. **Frontend – UI for QA Automation (React + Vite + Tailwind)**
   ממשק טסטרים שמאפשר:
   - הרצת תסריטים בלחיצה
   - צפייה ב-steps, logs, metadata
   - Dashboard עם סשנים פעילים
   - היסטוריית בדיקות עם פילטרים
   - ניהול סטאטוס בזמן אמת

המערכת בנויה לעבוד תחת עומס, עם כמה טסטרים וכמה ממירים במקביל.

---

## 2. תסריטי בדיקות QuickSet

### 2.1 TV_AUTO_SYNC
תסריט קריטי להצלבת שלט-טלוויזיה אוטומטית:

**שלבים מרכזיים:**
1. מעבר למסך הבית של Android TV
2. ניווט ל־Settings → Remote & Accessories → PartnerRC
3. בחירה ב־“Pair TV”
4. QuickSet מתחיל Auto-Scan
5. זיהוי יצרן טלוויזיה (Manufacturer)
6. בדיקת שליטה בעוצמת הקול (Volume Control)
7. בדיקת OSD – האם OSD של הטלוויזיה מופיע
8. בדיקה שלא מופיעים מסכי Pairing מיותרים
9. תיעוד תוצאות Pass/Fail

**תקלות מוכרות:**
- Volume לא מגיב
- OSD לא נכון (ממיר במקום טלוויזיה)
- Manufacturer מופיע בלי Model
- connectRC מופיע בטעות
- ערך `nes_volume_source` ב־ADB מחזיר `null`

---

### 2.2 REMOTE_PAIR_UNPAIR_FLOW
בדיקת חיבור/ניתוק השלט:

**כולל:**
- זיהוי PartnerRC כ־Connected
- ביצוע Unpair
- הופעת ConnectRC
- הופעת RC_Reboot
- תיקון באמצעות Home+Back
- בדיקת כל כפתורי השלט
- בדיקה שהשלט חוזר למצב תקין לאחר אתחול

---

### 2.3 BATTERY_STATUS
בדיקת סוללת שלט דרך Battery Analyzer:

**כולל:**
- איסוף נתוני מתח
- זיהוי battery_low
- זיהוי חריגות אנרגיה
- בדיקת דיווחי מערכת בלוגים

---

## 3. Backend – FastAPI Architecture

### 3.1 Endpoints מרכזיים

GET /health
POST /adb/connect
POST /infra/checks
POST /session/start
POST /session/step
POST /session/finish
GET /session/{session_id}
GET /session/{session_id}/logs
POST /qa/scenarios/run


### 3.2 Authentication
כל בקשה חייבת לכלול:


X-QuickSet-Api-Key: <tester-key>


כל טסטר עובד עם API Key משלו → מאפשר עומס מקבילי ללא התנגשות.

### 3.3 Session Structure
אובייקט Session כולל:
```json
{
  "session_id": "VS_123456",
  "tester_id": "tester-x",
  "stb_ip": "192.168.1.xxx",
  "scenario_name": "TV_AUTO_SYNC",
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
    "adb": "...",
    "logcat": "..."
  }
}

3.4 ADB Layer

המערכת מבצעת:

בדיקות חיבור

retry אוטומטי

ניתוקים "ריקים"

איסוף logcat

תיעוד כל פקודת adb בקובץ JSONL

4. UI for QA Automation – React Architecture
4.1 מבנה פרויקט מומלץ
src/
  api/
    client.ts
  components/
  hooks/
  pages/
  types/
  utils/

4.2 עמודים עיקריים
Dashboard

רשימת סשנים

פילטרים לפי Tester / IP / Scenario / Status

אינדיקציות של בריאות בדיקות

Session View

רשימת steps

pass / fail

viewer ל־logcat

כפתור “Run Again”

חיווי זמן אמת

Tester Settings

הזנת API Key

ברירות מחדל ל־STB IP

בדיקה מיידית של חיבור

4.3 קומפוננטים קריטיים

SessionCard

TestRunModal

ScenarioSelector

StepProgress

LogViewer

STBConnectionCard

4.4 UX Principles

כפתור יחיד להפעלת תסריט

שגיאות ברורות

Pass/Fail בצבעים בולטים

Log viewer בצד, לא במרכז

טסטר לא צריך “לשחזר” מידע – הכול מוצג

5. תמיכה במרובי טסטרים (Multi-Tester)

לכל טסטר API Key אישי

כל סשן מסומן לפי tester_id

אין מצב שבדיקות מתנגשות זו בזו

ריצה על כמה ממירים → כמה sessions → כל אחד עצמאי

מניעת override של סטאטוס או לוגים

6. תחקור תקלות נפוצות (מהעבודה האמיתית)
6.1 Volume לא מגיב
adb shell settings get global nes_volume_source
→ null


מקור: QuickSet החזיר נתון ריק → אין מקור עוצמה.
פתרון:

להריץ Auto Sync מחדש

לנקות RS cache

לאמת state של PartnerRC

6.2 connectRC מופיע בטעות

מקור:
רענון PartnerRC לא תקין / state stale.
פתרון:

השוואת logcat לפני/אחרי

בדיקת RC_Reboot

ניטור partnerRC scan intervals

6.3 Manufacturer ללא Model

מקור:
QuickSet DB לא מחזיר model בגלל timeout או קטיעת scan.
פתרון:

לבדוק תזמון scan בלוגים

להאריך Timeout

לראות אם מסך Auto Sync נסגר מהר מדי

7. כללי יציבות פיתוח

כל קובץ שחוזר למשתמש חייב להיות מלא ומוכן להרצה.

שמות חייבים להיות אחידים — API ↔ UI ↔ Backend.

אין להשאיר TODO או קטעים “שמשתמש ימלא בעצמו”.

שמירה על מבנה JSON יציב.

תמיכה ב-parallel execution בלי התנגשויות.

8. ארכיטקטורת קוד מומלצת
Frontend

TypeScript מלא

Zustand/Redux לניהול state

API client אחיד

מודולים קטנים, חדים, testable

Backend

services/ ללוגיקה

adb/ לשכבת תקשורת

schemas/ ל-Pydantic

logging/ ל-JSONL structured logs

utils/ לכלים משותפים

9. כללים למודל (לשימוש ה-GPT)

כל בקשת קוד → להחזיר קובץ מלא.

כל שינוי → לשמור עקביות עם ה-knowledge.

תמיד לחשוב על multi-tester & multi-device.

להציע refactor כשזה מונע תקלות עתידיות.

לא לבקש מהמשתמש “לצרף חלקים” — להחזיר סט מלא.
