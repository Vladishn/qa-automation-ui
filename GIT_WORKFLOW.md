# Git Workflow – qa-automation-ui

תהליך עבודה מסודר עם Git ו-GitHub עבור הפרויקט `qa-automation-ui`.

המטרה: לשמור על קוד נקי, סדר ברור, וסנכרון מלא בין המחשב המקומי לבין GitHub.

---

## 1. עקרונות בסיס

- עובדים על הענף `main`.
- כל שינוי:  
  **Commit → Push**  
- לשמור הודעות Commit ברורות וקצרות.
- Pull נדרש רק אם GitHub מקדים אותך (למשל לאחר עריכה דרך הדפדפן או מחשב אחר).

---

## 2. זרימת עבודה יומית – Checklist קצר

1. פותחים את הפרויקט ב-VS Code.  
2. בודקים אם יש צורך ב-Pull:  
   - אם VS Code מציג ⬇ או הודעה שצריך למשוך → מבצעים Pull.  
3. עורכים את הקוד.  
4. ב-Source Control כותבים הודעת Commit ולוחצים **Commit**.  
5. לוחצים על החץ למעלה (**Push / Sync Changes**) כדי להעלות ל-GitHub.  
6. מוודאים שאין שינויים ממתינים.

---

## 3. מתי צריך Pull?

Pull נדרש רק אם:

- עדכנת קבצים ישירות ב-GitHub (דרך דפדפן).
- עבדת על אותו repo ממחשב אחר.  
- VS Code מציג התראה שיש שינויים ב-origin/main.

בכל מצב אחר:  
**לא חייבים Pull** — רק Commit + Push.

---

## 4. איך כותבים Commit טוב?

הודעת Commit צריכה לענות על השאלה:  
“מה בדיוק שיניתי עכשיו?”

דוגמאות מומלצות:

- `add adb retry logic in backend service`
- `update UI layout for test runner`
- `fix websocket reconnect handling`
- `refactor tv_auto_sync controller`

דוגמאות לא טובות:

- `update`
- `test`
- `fix`
- `changes`

---

## 5. מה קורה מאחורי הקלעים?

### Commit
- VS Code מבצע Stage אוטומטי.
- Git יוצר snapshot חדש.
- `HEAD` זז לקומיט האחרון על `main`.

### Push
- מעלה את הקומיטים ל־`origin/main`.
- בסיום:  
  `main` ≡ `origin/main`.

### Pull
- מביא עדכונים מרוחקים (Fetch).
- ממזג לתוך העבודה המקומית (Merge).

---

## 6. כש-Push נכשל (Rejected)

הסיבה:  
ב־GitHub קיימים commits שלא אצלך.

תהליך פתרון:

1. מבצעים **Pull**.  
2. אם יש קונפליקטים — VS Code יסמן קבצים.  
3. פותרים קונפליקטים ושומרים.  
4. עושים Commit חדש (שמכיל את פתרון הקונפליקט).  
5. מבצעים Push.

---

## 7. רצף סטנדרטי לכל שינוי

עריכת קוד
↓
Commit עם הודעה ברורה
↓
Push ל-GitHub

yaml
Copy code

---

## 8. טיפים חשובים

- לעשות Commits קטנים ולוגיים.
- לא לערבב כמה נושאים ב-Commit אחד.
- לשמור על repo מסונכרן:  
  כמה שפחות פערים בין `main` ל־`origin/main`.

---
