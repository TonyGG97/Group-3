"""Storage backends. Both guarantee: a name can only be saved once, and a group never exceeds its capacity."""
import os
import sqlite3
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.eat).strftime("%Y-%m-%d %H:%M:%S UTC")


class SQLiteStore:
    """Local/testing backend. NOT durable on Streamlit Community Cloud (the disk resets on restart)."""
    durable = False

    def __init__(self, path=None):
        self.path = path or os.environ.get("PICKS_DB", "picks.db")
        con = self._con()
        con.execute("CREATE TABLE IF NOT EXISTS picks (name TEXT PRIMARY KEY, grp INTEGER NOT NULL, ts TEXT NOT NULL)")
        con.commit()
        con.close()

    def _con(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        return con

    def all(self):
        con = self._con()
        rows = con.execute("SELECT name, grp, ts FROM picks ORDER BY ts, name").fetchall()
        con.close()
        return [{"name": n, "group": g, "ts": t} for n, g, t in rows]

    def add(self, name, group, cap):
        con = self._con()
        try:
            con.execute("BEGIN IMMEDIATE")  # takes the write lock: check + insert is atomic
            if con.execute("SELECT 1 FROM picks WHERE name=?", (name,)).fetchone():
                con.execute("ROLLBACK")
                return False, "already"
            n = con.execute("SELECT COUNT(*) FROM picks WHERE grp=?", (group,)).fetchone()[0]
            if n >= cap:
                con.execute("ROLLBACK")
                return False, "full"
            con.execute("INSERT INTO picks (name, grp, ts) VALUES (?,?,?)", (name, group, _now()))
            con.execute("COMMIT")
            return True, "ok"
        except Exception:
            try:
                con.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            con.close()

    def delete(self, name):
        con = self._con()
        con.execute("DELETE FROM picks WHERE name=?", (name,))
        con.close()


class SheetsStore:
    """Durable backend: a Google Sheet. Append-then-verify keeps it consistent even if two people submit at once."""
    durable = True
    HEADER = ["Name", "Group", "Timestamp", "ID"]

    def __init__(self, creds: dict, sheet_id: str, caps: dict, worksheet="picks"):
        import gspread
        gc = gspread.service_account_from_dict(dict(creds))
        sh = gc.open_by_key(sheet_id)
        try:
            self.ws = sh.worksheet(worksheet)
        except gspread.WorksheetNotFound:
            self.ws = sh.add_worksheet(worksheet, rows=200, cols=4)
        if self.ws.row_values(1) != self.HEADER:
            self.ws.update(range_name="A1:D1", values=[self.HEADER])
        self.caps = caps

    def _rows(self):
        return self.ws.get_all_values()[1:]

    def _classify(self, rows):
        """Walk rows in sheet order. A row counts only if its name is new and its group still has room."""
        seen, count, out = set(), {}, []
        for r in rows:
            r = (r + ["", "", "", ""])[:4]
            name, grp = r[0], int(r[1]) if str(r[1]).isdigit() else 0
            if not name or grp not in self.caps:
                out.append((r, "invalid")); continue
            if name in seen:
                out.append((r, "already")); continue
            if count.get(grp, 0) >= self.caps[grp]:
                out.append((r, "full")); continue
            seen.add(name); count[grp] = count.get(grp, 0) + 1
            out.append((r, "ok"))
        return out

    def all(self):
        return [{"name": r[0], "group": int(r[1]), "ts": r[2]} for r, v in self._classify(self._rows()) if v == "ok"]

    def add(self, name, group, cap):
        token = uuid.uuid4().hex
        self.ws.append_row([name, group, _now(), token], value_input_option="RAW")
        for idx, (r, verdict) in enumerate(self._classify(self._rows())):
            if r[3] == token:
                if verdict == "ok":
                    return True, "ok"
                self.ws.delete_rows(idx + 2)  # roll back our own losing row
                return False, verdict
        return False, "error"

    def delete(self, name):
        rows = self._rows()
        for i in range(len(rows), 0, -1):
            if rows[i - 1][0] == name:
                self.ws.delete_rows(i + 1)
