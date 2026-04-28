import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import psycopg2

DB = dict(dbname="postgres", user="postgres", password="postgres",
          host="localhost", port=5432)

def conn():
    return psycopg2.connect(**DB)

def fetchall(sql, params=()):
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def execute(sql, params=()):
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
        c.commit()

def hospital_map():
    rows = fetchall("SELECT id, name FROM hospitals ORDER BY name")
    return {r[1]: r[0] for r in rows}, [r[1] for r in rows]

def department_map(hospital_id=None):
    if hospital_id:
        rows = fetchall(
            "SELECT d.id, h.name||' / '||d.name "
            "FROM departments d JOIN hospitals h ON h.id=d.hospital_id "
            "WHERE d.hospital_id=%s ORDER BY d.name", (hospital_id,))
    else:
        rows = fetchall(
            "SELECT d.id, h.name||' / '||d.name "
            "FROM departments d JOIN hospitals h ON h.id=d.hospital_id "
            "ORDER BY h.name, d.name")
    return {r[1]: r[0] for r in rows}, [r[1] for r in rows]

def position_map():
    rows = fetchall("SELECT id, title FROM positions ORDER BY title")
    return {r[1]: r[0] for r in rows}, [r[1] for r in rows]

def diagnosis_map():
    rows = fetchall("SELECT id, code||' - '||name FROM diagnoses ORDER BY code")
    return {r[1]: r[0] for r in rows}, [r[1] for r in rows]

def doctor_map():
    rows = fetchall(
        "SELECT d.id, d.last_name||' '||d.first_name||' ('||COALESCE(p.title,'')||')' "
        "FROM doctors d LEFT JOIN positions p ON p.id=d.position_id ORDER BY d.last_name")
    return {r[1]: r[0] for r in rows}, [r[1] for r in rows]


class InputDialog(tk.Toplevel):
    def __init__(self, parent, title, fields, values=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self._vars = {}
        fr = tk.Frame(self, padx=14, pady=10)
        fr.pack(fill="both", expand=True)
        for i, (lbl, key, wtype, opts) in enumerate(fields):
            tk.Label(fr, text=lbl, anchor="w").grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            cur_val = (values or {}).get(key, "")
            if wtype == "entry":
                var = tk.StringVar(value=cur_val)
                tk.Entry(fr, textvariable=var, width=36).grid(
                    row=i, column=1, sticky="ew", pady=3)
            elif wtype == "combo":
                var = tk.StringVar(value=cur_val)
                ttk.Combobox(fr, textvariable=var, values=opts,
                             width=34, state="readonly").grid(
                    row=i, column=1, sticky="ew", pady=3)
            elif wtype == "spinbox":
                var = tk.StringVar(value=cur_val or str(opts[0]))
                tk.Spinbox(fr, from_=opts[0], to=opts[1],
                           textvariable=var, width=34).grid(
                    row=i, column=1, sticky="ew", pady=3)
            self._vars[key] = var
        bf = tk.Frame(fr)
        bf.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
        tk.Button(bf, text="OK",     width=10, command=self._ok).pack(side="left", padx=4)
        tk.Button(bf, text="Отмена", width=10, command=self.destroy).pack(side="left", padx=4)
        self.grab_set()
        self.wait_window()

    def _ok(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class FilterSortBar(tk.Frame):
    def __init__(self, master, columns, on_apply, on_reset):
        super().__init__(master)
        tk.Label(self, text="Поиск:").pack(side="left", padx=(4, 2))
        self.search_var = tk.StringVar()
        tk.Entry(self, textvariable=self.search_var, width=22).pack(side="left", padx=2)

        tk.Label(self, text="Сортировка:").pack(side="left", padx=(10, 2))
        self.sort_var = tk.StringVar()
        ttk.Combobox(self, textvariable=self.sort_var, values=columns,
                     width=20, state="readonly").pack(side="left", padx=2)
        if columns:
            self.sort_var.set(columns[0])

        self.sort_dir = tk.StringVar(value="По возрастанию")
        ttk.Combobox(self, textvariable=self.sort_dir,
                     values=["По возрастанию", "По убыванию"],
                     width=16, state="readonly").pack(side="left", padx=2)

        tk.Button(self, text="Применить", command=on_apply).pack(side="left", padx=6)
        tk.Button(self, text="Сброс",     command=on_reset).pack(side="left", padx=2)



class BaseTab(tk.Frame):
    columns   = []
    sort_cols = []
    tab_name  = ""

    def __init__(self, master):
        super().__init__(master)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.filter_bar = FilterSortBar(
            self, self.sort_cols,
            on_apply=self._apply_filter,
            on_reset=self.refresh)
        self.filter_bar.pack(fill="x", padx=6, pady=(6, 0))

        btn_bar = tk.Frame(self)
        btn_bar.pack(fill="x", padx=6, pady=(4, 0))
        for txt, cmd in [("Добавить", self.add),
                         ("Изменить", self.edit),
                         ("Удалить",  self.delete)]:
            tk.Button(btn_bar, text=txt, width=11, command=cmd).pack(side="left", padx=3)

        fr = tk.Frame(self)
        fr.pack(fill="both", expand=True, padx=6, pady=6)
        cols = [c[1] for c in self.columns]
        self.tree = ttk.Treeview(fr, columns=cols, show="headings", selectmode="browse")
        for hdr, cid, w in self.columns:
            self.tree.heading(cid, text=hdr,
                              command=lambda c=cid: self._sort_by(c))
            self.tree.column(cid, width=w, minwidth=30)
        vsb = ttk.Scrollbar(fr, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(fr, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self._sort_col = None
        self._sort_asc = True

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rows.sort(reverse=not self._sort_asc,
                  key=lambda x: x[0].lower() if x[0] else "")
        for i, (_, k) in enumerate(rows):
            self.tree.move(k, "", i)

    def _apply_filter(self):
        q    = self.filter_bar.search_var.get().strip().lower()
        scol = self.filter_bar.sort_var.get()
        sdir = "По убыванию" if self.filter_bar.sort_dir.get() == "По убыванию" else "По возрастанию"
        self.refresh(search=q, sort_col=scol, sort_dir=sdir)

    def selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Выбор", "Выберите запись.")
            return None
        return self.tree.item(sel[0])["values"][0]

    def _load(self, rows):
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", values=list(r))

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        pass
    def add(self):    pass
    def edit(self):   pass
    def delete(self): pass


class HospitalsTab(BaseTab):
    tab_name  = "Больницы"
    columns   = [("ID",      "id",    45),
                 ("Название","name", 260),
                 ("Адрес",   "addr", 300),
                 ("Телефон", "phone",150)]
    sort_cols = ["ID", "Название", "Адрес", "Телефон"]

    def _sql_col(self, label):
        return {"ID":"id","Название":"name","Адрес":"address","Телефон":"phone"
                }.get(label, "id")

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = self._sql_col(sort_col) if sort_col else "id"
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        base = "SELECT id, name, address, phone FROM hospitals "
        if search:
            rows = fetchall(
                base + f"WHERE LOWER(COALESCE(name||' '||COALESCE(address,''),'')) LIKE %s ORDER BY {sc} {sd}",
                (f"%{search}%",))
        else:
            rows = fetchall(base + f"ORDER BY {sc} {sd}")
        self._load(rows)

    def _fields(self):
        return [("Название",       "name",  "entry", None),
                ("ИНН (10 цифр)", "inn",   "entry", None),
                ("Адрес",          "addr",  "entry", None),
                ("Телефон",        "phone", "entry", None)]

    def add(self):
        dlg = InputDialog(self, "Добавить больницу", self._fields())
        if not dlg.result: return
        d = dlg.result
        try:
            execute("INSERT INTO hospitals(name,inn,address,phone) VALUES(%s,%s,%s,%s)",
                    (d["name"], d["inn"] or None, d["addr"] or None,
                     d["phone"] or "не указан"))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall("SELECT name,inn,address,phone FROM hospitals WHERE id=%s", (rid,))[0]
        v = {"name": row[0], "inn": row[1] or "", "addr": row[2] or "", "phone": row[3] or ""}
        dlg = InputDialog(self, "Изменить больницу", self._fields(), v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("UPDATE hospitals SET name=%s,inn=%s,address=%s,phone=%s WHERE id=%s",
                    (d["name"], d["inn"] or None, d["addr"] or None,
                     d["phone"] or "не указан", rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить больницу и все связанные данные?"):
            execute("DELETE FROM hospitals WHERE id=%s", (rid,))
            self.refresh()


class DepartmentsTab(BaseTab):
    tab_name  = "Отделения"
    columns   = [("ID",             "id",   45),
                 ("Больница",       "hosp", 230),
                 ("Отделение",      "name", 200),
                 ("Зав. отделением","head", 180),
                 ("Этаж",           "floor", 55),
                 ("Коек",           "beds",  55)]
    sort_cols = ["ID", "Больница", "Отделение", "Зав. отделением", "Этаж"]

    def _sql_col(self, label):
        return {"ID":"d.id","Больница":"h.name","Отделение":"d.name",
                "Зав. отделением":"d.head_name","Этаж":"d.floor"}.get(label, "d.id")

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = self._sql_col(sort_col) if sort_col else "d.id"
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        base = ("SELECT d.id, h.name, d.name, d.head_name, d.floor, d.bed_count "
                "FROM departments d JOIN hospitals h ON h.id=d.hospital_id ")
        if search:
            rows = fetchall(
                base + f"WHERE LOWER(COALESCE(d.name||' '||h.name,'')) LIKE %s ORDER BY {sc} {sd}",
                (f"%{search}%",))
        else:
            rows = fetchall(base + f"ORDER BY {sc} {sd}")
        self._load(rows)

    def _fields(self):
        hmap, hnames = hospital_map()
        fields = [("Больница",           "hosp",  "combo",   hnames),
                  ("Название отделения", "name",  "entry",   None),
                  ("Зав. отделением",    "head",  "entry",   None),
                  ("Этаж",               "floor", "spinbox", (1, 20)),
                  ("Число коек",         "beds",  "spinbox", (0, 200))]
        return fields, hmap

    def add(self):
        fields, hmap = self._fields()
        dlg = InputDialog(self, "Добавить отделение", fields)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("INSERT INTO departments(hospital_id,name,head_name,floor,bed_count) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (hmap.get(d["hosp"]), d["name"], d["head"] or "вакансия",
                     d["floor"] or 1, d["beds"] or 0))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall(
            "SELECT d.hospital_id,d.name,d.head_name,d.floor,d.bed_count,h.name "
            "FROM departments d JOIN hospitals h ON h.id=d.hospital_id WHERE d.id=%s", (rid,))[0]
        fields, hmap = self._fields()
        v = {"hosp": row[5], "name": row[1], "head": row[2] or "",
             "floor": str(row[3]), "beds": str(row[4])}
        dlg = InputDialog(self, "Изменить отделение", fields, v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("UPDATE departments SET hospital_id=%s,name=%s,head_name=%s,"
                    "floor=%s,bed_count=%s WHERE id=%s",
                    (hmap.get(d["hosp"]), d["name"], d["head"] or "вакансия",
                     d["floor"], d["beds"], rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить отделение?"):
            execute("DELETE FROM departments WHERE id=%s", (rid,))
            self.refresh()


class PositionsTab(BaseTab):
    tab_name  = "Должности"
    columns   = [("ID",          "id",    45),
                 ("Должность",   "title", 280),
                 ("Неопходимый cтаж для должности",  "exp",   110)]
    sort_cols = ["ID", "Должность", "Стаж (лет)"]

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = {"ID":"id","Должность":"title","Стаж (лет)":"salary_base"
              }.get(sort_col, "id")
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        if search:
            rows = fetchall( f"SELECT id, title, salary_base::INT FROM positions "
                             f"WHERE LOWER(title) LIKE %s ORDER BY {sc} {sd}", (f"%{search}%",))
        else:
            rows = fetchall( f"SELECT id, title, salary_base::INT FROM positions ORDER BY {sc} {sd}")
        self._load(rows)

    def add(self):
        dlg = InputDialog(self, "Добавить должность",
                          [("Название",        "title", "entry",   None),
                           ("Мин. стаж (лет)", "exp",   "spinbox", (0, 50))])
        if not dlg.result: return
        d = dlg.result
        try:
            execute("INSERT INTO positions(title, salary_base) VALUES(%s,%s)",
                    (d["title"], d.get("exp") or 0))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall("SELECT title, salary_base FROM positions WHERE id=%s", (rid,))[0]
        v = {"title": row[0], "exp": str(int(row[1] or 0))}
        dlg = InputDialog(self, "Изменить должность",
                          [("Название",        "title", "entry",   None),
                           ("Мин. стаж (лет)", "exp",   "spinbox", (0, 50))], v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("UPDATE positions SET title=%s, salary_base=%s WHERE id=%s",
                    (d["title"], d.get("exp") or 0, rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить должность?"):
            execute("DELETE FROM positions WHERE id=%s", (rid,))
            self.refresh()


class DiagnosesTab(BaseTab):
    tab_name  = "Диагнозы"
    columns   = [("ID",       "id",    45),
                 ("Код МКБ",  "code",  80),
                 ("Название", "name", 220),
                 ("Тяжесть",  "sev",   70),
                 ("Методика", "treat",320)]
    sort_cols = ["ID", "Код МКБ", "Название", "Тяжесть"]

    def _sql_col(self, label):
        return {"ID":"id","Код МКБ":"code","Название":"name","Тяжесть":"severity"
                }.get(label, "id")

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = self._sql_col(sort_col) if sort_col else "id"
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        if search:
            rows = fetchall(
                f"SELECT id, code, name, severity, treatment FROM diagnoses "
                f"WHERE LOWER(COALESCE(name||' '||code,'')) LIKE %s ORDER BY {sc} {sd}",
                (f"%{search}%",))
        else:
            rows = fetchall(
                f"SELECT id, code, name, severity, treatment FROM diagnoses ORDER BY {sc} {sd}")
        self._load(rows)

    def add(self):
        dlg = InputDialog(self, "Добавить диагноз",
                          [("Код МКБ",         "code",  "entry",   None),
                           ("Название",         "name",  "entry",   None),
                           ("Тяжесть (1-5)",    "sev",   "spinbox", (1, 5)),
                           ("Методика лечения", "treat", "entry",   None)])
        if not dlg.result: return
        d = dlg.result
        try:
            execute("INSERT INTO diagnoses(code,name,severity,treatment) VALUES(%s,%s,%s,%s)",
                    (d["code"], d["name"], d["sev"] or 1, d["treat"] or None))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall(
            "SELECT code,name,severity,treatment FROM diagnoses WHERE id=%s", (rid,))[0]
        v = {"code": row[0], "name": row[1], "sev": str(row[2]), "treat": row[3] or ""}
        dlg = InputDialog(self, "Изменить диагноз",
                          [("Код МКБ",         "code",  "entry",   None),
                           ("Название",         "name",  "entry",   None),
                           ("Тяжесть (1-5)",    "sev",   "spinbox", (1, 5)),
                           ("Методика лечения", "treat", "entry",   None)], v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("UPDATE diagnoses SET code=%s,name=%s,severity=%s,treatment=%s WHERE id=%s",
                    (d["code"], d["name"], d["sev"], d["treat"] or None, rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить диагноз?"):
            execute("DELETE FROM diagnoses WHERE id=%s", (rid,))
            self.refresh()


class DoctorsTab(BaseTab):
    tab_name  = "Врачи"
    columns   = [("ID",         "id",    45),
                 ("Фамилия",    "ln",   110),
                 ("Имя",        "fn",    90),
                 ("Отчество",   "mn",   130),
                 ("Должность",  "pos",  130),
                 ("Кабинет",    "cab",   65),
                 ("Стаж (лет)", "exp",   75),
                 ("Больница",   "hosp", 200),
                 ("Отделение",  "dept", 190),
                 ("Пациентов",  "pcnt",  75)]
    sort_cols = ["ID", "Фамилия", "Должность", "Стаж (лет)", "Больница", "Отделение"]

    def _sql_col(self, label):
        return {"ID":"d.id","Фамилия":"d.last_name","Должность":"p.title",
                "Стаж (лет)":"d.hire_date","Больница":"h.name","Отделение":"dep.name"
                }.get(label, "d.id")

    def _base_sql(self):
        return ("SELECT d.id, d.last_name, d.first_name, d.middle_name,"
                " p.title, d.cabinet,"
                " DATE_PART('year', AGE(d.hire_date))::INT AS exp_years,"
                " h.name, dep.name, d.patient_count "
                "FROM doctors d "
                "LEFT JOIN positions   p   ON p.id   = d.position_id "
                "LEFT JOIN hospitals   h   ON h.id   = d.hospital_id "
                "LEFT JOIN departments dep ON dep.id = d.department_id ")

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = self._sql_col(sort_col) if sort_col else "d.id"
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        if search:
            rows = fetchall(
                self._base_sql() +
                "WHERE LOWER(COALESCE(d.last_name||' '||d.first_name,'')) LIKE %s "
                f"ORDER BY {sc} {sd}", (f"%{search}%",))
        else:
            rows = fetchall(self._base_sql() + f"ORDER BY {sc} {sd}")
        self._load(rows)

    def _fields(self):
        hmap, hnames = hospital_map()
        dmap, dnames = department_map()
        pmap, pnames = position_map()
        fields = [("Фамилия",                 "ln",   "entry",   None),
                  ("Имя",                      "fn",   "entry",   None),
                  ("Отчество",                 "mn",   "entry",   None),
                  ("ИНН (12 цифр)",            "inn",  "entry",   None),
                  ("Должность",                "pos",  "combo",   pnames),
                  ("Кабинет",                  "cab",  "entry",   None),
                  ("Больница",                 "hosp", "combo",   hnames),
                  ("Отделение",                "dept", "combo",   dnames),
                  ("Дата найма (ГГГГ-ММ-ДД)", "hire", "entry",   None)]
        return fields, hmap, dmap, pmap

    def add(self):
        fields, hmap, dmap, pmap = self._fields()
        dlg = InputDialog(self, "Добавить врача", fields)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("INSERT INTO doctors(last_name,first_name,middle_name,inn,"
                    "position_id,cabinet,hospital_id,department_id,hire_date) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (d["ln"], d["fn"], d["mn"] or None, d["inn"] or None,
                     pmap.get(d["pos"]), d["cab"] or "-",
                     hmap.get(d["hosp"]), dmap.get(d["dept"]),
                     d["hire"] or str(date.today())))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall(
            "SELECT d.last_name,d.first_name,d.middle_name,d.inn,"
            "d.position_id,d.cabinet,d.hospital_id,d.department_id,d.hire_date,"
            "p.title, h.name, dep.name "
            "FROM doctors d "
            "LEFT JOIN positions   p   ON p.id   = d.position_id "
            "LEFT JOIN hospitals   h   ON h.id   = d.hospital_id "
            "LEFT JOIN departments dep ON dep.id = d.department_id WHERE d.id=%s",
            (rid,))[0]
        v = {"ln": row[0], "fn": row[1], "mn": row[2] or "", "inn": row[3] or "",
             "pos":  row[9] or "", "cab": row[5] or "",
             "hosp": row[10] or "", "dept": row[11] or "",
             "hire": str(row[8]) if row[8] else ""}
        fields, hmap, dmap, pmap = self._fields()
        dlg = InputDialog(self, "Изменить врача", fields, v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute("UPDATE doctors SET last_name=%s,first_name=%s,middle_name=%s,inn=%s,"
                    "position_id=%s,cabinet=%s,hospital_id=%s,department_id=%s,hire_date=%s "
                    "WHERE id=%s",
                    (d["ln"], d["fn"], d["mn"] or None, d["inn"] or None,
                     pmap.get(d["pos"]), d["cab"] or "-",
                     hmap.get(d["hosp"]), dmap.get(d["dept"]),
                     d["hire"] or str(date.today()), rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить врача?"):
            execute("DELETE FROM doctors WHERE id=%s", (rid,))
            self.refresh()


class PatientsTab(BaseTab):
    tab_name  = "Пациенты"
    columns   = [("ID",             "id",     45),
                 ("Фамилия",        "ln",    110),
                 ("Имя",            "fn",     90),
                 ("Отчество",       "mn",    130),
                 ("Д.р.",           "birth",  85),
                 ("Полис",          "ins",   100),
                 ("Госпитализация", "adm",   100),
                 ("Выписка",        "dis",    90),
                 ("Статус",         "status", 90),
                 ("Диагноз",        "diag",  170),
                 ("Врач",           "doc",   160),
                 ("Отделение",      "dept",  170),
                 ("Больница",       "hosp",  200)]
    sort_cols = ["ID","Фамилия","Госпитализация","Выписка","Статус",
                 "Диагноз","Врач","Больница"]
    STATUSES  = ["на лечении", "выписан", "переведён", "умер"]

    def _sql_col(self, label):
        return {"ID":"p.id","Фамилия":"p.last_name","Госпитализация":"p.admission_date",
                "Выписка":"p.discharge_date","Статус":"p.discharge_status",
                "Диагноз":"dg.name","Врач":"d.last_name","Больница":"h.name"
                }.get(label, "p.id")

    def _base_sql(self):
        return ("SELECT p.id, p.last_name, p.first_name, p.middle_name,"
                " p.birth_date, p.insurance_num, p.admission_date, p.discharge_date,"
                " p.discharge_status, dg.name,"
                " d.last_name||' '||d.first_name,"
                " dep.name, h.name "
                "FROM patients p "
                "LEFT JOIN diagnoses   dg  ON dg.id  = p.diagnosis_id "
                "LEFT JOIN doctors     d   ON d.id   = p.doctor_id "
                "LEFT JOIN departments dep ON dep.id = p.department_id "
                "LEFT JOIN hospitals   h   ON h.id   = p.hospital_id ")

    def refresh(self, search="", sort_col="", sort_dir="По возрастанию"):
        sc = self._sql_col(sort_col) if sort_col else "p.id"
        sd = "DESC" if sort_dir == "По убыванию" else "ASC"
        if search:
            rows = fetchall(
                self._base_sql() +
                "WHERE LOWER(COALESCE(p.last_name||' '||p.first_name,'')) LIKE %s "
                f"ORDER BY {sc} {sd}", (f"%{search}%",))
        else:
            rows = fetchall(self._base_sql() + f"ORDER BY {sc} {sd}")
        self._load(rows)

    def _fields(self):
        hmap,   hnames   = hospital_map()
        dmap,   dnames   = department_map()
        docmap, docnames = doctor_map()
        dgmap,  dgnames  = diagnosis_map()
        fields = [
            ("Фамилия",                    "ln",     "entry",   None),
            ("Имя",                        "fn",     "entry",   None),
            ("Отчество",                   "mn",     "entry",   None),
            ("ИНН (12 цифр)",              "inn",    "entry",   None),
            ("Дата рождения (ГГГГ-ММ-ДД)", "birth",  "entry",   None),
            ("Номер полиса",               "ins",    "entry",   None),
            ("Дата госпитализации",        "adm",    "entry",   None),
            ("Дата выписки",               "dis",    "entry",   None),
            ("Статус",                     "status", "combo",   self.STATUSES),
            ("Дата диагноза",              "ddate",  "entry",   None),
            ("Диагноз",                    "diag",   "combo",   dgnames),
            ("Врач",                       "doc",    "combo",   docnames),
            ("Больница",                   "hosp",   "combo",   hnames),
            ("Отделение",                  "dept",   "combo",   dnames),
        ]
        return fields, hmap, dmap, docmap, dgmap

    def add(self):
        fields, hmap, dmap, docmap, dgmap = self._fields()
        dlg = InputDialog(self, "Добавить пациента", fields)
        if not dlg.result: return
        d = dlg.result
        try:
            execute(
                "INSERT INTO patients(last_name,first_name,middle_name,inn,"
                "birth_date,insurance_num,admission_date,discharge_date,"
                "discharge_status,diagnosis_date,diagnosis_id,"
                "doctor_id,hospital_id,department_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (d["ln"], d["fn"], d["mn"] or None, d["inn"] or None,
                 d["birth"] or None, d["ins"] or None,
                 d["adm"] or str(date.today()), d["dis"] or None,
                 d["status"] or "на лечении", d["ddate"] or None,
                 dgmap.get(d["diag"]), docmap.get(d["doc"]),
                 hmap.get(d["hosp"]), dmap.get(d["dept"])))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def edit(self):
        rid = self.selected_id()
        if rid is None: return
        row = fetchall(
            "SELECT p.last_name,p.first_name,p.middle_name,p.inn,"
            "p.birth_date,p.insurance_num,p.admission_date,p.discharge_date,"
            "p.discharge_status,p.diagnosis_date,"
            "dg.code||' - '||dg.name,"
            "d.last_name||' '||d.first_name||' ('||COALESCE(pos.title,'')||')',"
            "h.name, dep.name "
            "FROM patients p "
            "LEFT JOIN diagnoses   dg  ON dg.id  = p.diagnosis_id "
            "LEFT JOIN doctors     d   ON d.id   = p.doctor_id "
            "LEFT JOIN positions   pos ON pos.id = d.position_id "
            "LEFT JOIN departments dep ON dep.id = p.department_id "
            "LEFT JOIN hospitals   h   ON h.id   = p.hospital_id "
            "WHERE p.id=%s", (rid,))[0]
        v = {"ln": row[0], "fn": row[1], "mn": row[2] or "", "inn": row[3] or "",
             "birth":  str(row[4]) if row[4] else "",
             "ins":    row[5] or "",
             "adm":    str(row[6]) if row[6] else "",
             "dis":    str(row[7]) if row[7] else "",
             "status": row[8] or "на лечении",
             "ddate":  str(row[9]) if row[9] else "",
             "diag":   row[10] or "", "doc":  row[11] or "",
             "hosp":   row[12] or "", "dept": row[13] or ""}
        fields, hmap, dmap, docmap, dgmap = self._fields()
        dlg = InputDialog(self, "Изменить пациента", fields, v)
        if not dlg.result: return
        d = dlg.result
        try:
            execute(
                "UPDATE patients SET last_name=%s,first_name=%s,middle_name=%s,inn=%s,"
                "birth_date=%s,insurance_num=%s,admission_date=%s,discharge_date=%s,"
                "discharge_status=%s,diagnosis_date=%s,"
                "diagnosis_id=%s,doctor_id=%s,hospital_id=%s,department_id=%s WHERE id=%s",
                (d["ln"], d["fn"], d["mn"] or None, d["inn"] or None,
                 d["birth"] or None, d["ins"] or None,
                 d["adm"] or str(date.today()), d["dis"] or None,
                 d["status"] or "на лечении", d["ddate"] or None,
                 dgmap.get(d["diag"]), docmap.get(d["doc"]),
                 hmap.get(d["hosp"]), dmap.get(d["dept"]), rid))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def delete(self):
        rid = self.selected_id()
        if rid is None: return
        if messagebox.askyesno("Удаление", "Удалить пациента?"):
            execute("DELETE FROM patients WHERE id=%s", (rid,))
            self.refresh()


class ReportWindow(tk.Toplevel):
    def __init__(self, parent, title, sql, params, col_headers):
        super().__init__(parent)
        self.title(title)
        self.geometry("1060x520")
        cols = [f"c{i}" for i in range(len(col_headers))]
        tree = ttk.Treeview(self, columns=cols, show="headings")
        for i, h in enumerate(col_headers):
            tree.heading(f"c{i}", text=h)
            tree.column(f"c{i}", width=max(80, len(h)*11), minwidth=40)
        vsb = ttk.Scrollbar(self, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        try:
            rows = fetchall(sql, params)
            for r in rows:
                tree.insert("", "end",
                            values=[str(x) if x is not None else "" for x in r])
            tk.Label(self, text=f"Найдено записей: {len(rows)}",
                     anchor="w").pack(fill="x", padx=6, pady=4)
        except Exception as e:
            messagebox.showerror("Ошибка отчёта", str(e))


def report_patients_by_doctor(parent):
    _, docnames = doctor_map()
    if not docnames:
        messagebox.showinfo("Нет данных", "Нет врачей в базе.")
        return
    win = tk.Toplevel(parent)
    win.title("Отчёт 1 — Пациенты врача за период")
    win.resizable(False, False)

    tk.Label(win, text="Врач:").grid(row=0, column=0, padx=10, pady=6, sticky="w")
    doc_var = tk.StringVar(value=docnames[0])
    ttk.Combobox(win, textvariable=doc_var, values=docnames,
                 width=40, state="readonly").grid(row=0, column=1, columnspan=2,
                                                  pady=6, padx=4, sticky="w")
    tk.Label(win, text="Дата с (ГГГГ-ММ-ДД):").grid(row=1, column=0, padx=10, pady=6, sticky="w")
    d1 = tk.StringVar(value="2025-01-01")
    tk.Entry(win, textvariable=d1, width=16).grid(row=1, column=1, pady=6, padx=4, sticky="w")

    tk.Label(win, text="Дата по (ГГГГ-ММ-ДД):").grid(row=2, column=0, padx=10, pady=6, sticky="w")
    d2 = tk.StringVar(value=str(date.today()))
    tk.Entry(win, textvariable=d2, width=16).grid(row=2, column=1, pady=6, padx=4, sticky="w")

    tk.Label(win, text="Сортировка:").grid(row=3, column=0, padx=10, pady=6, sticky="w")
    sort_var = tk.StringVar(value="Фамилия")
    ttk.Combobox(win, textvariable=sort_var,
                 values=["Фамилия","Дата госпитализации","Диагноз","Статус"],
                 width=24, state="readonly").grid(row=3, column=1, pady=6, padx=4, sticky="w")
    sort_dir = tk.StringVar(value="По возрастанию")
    ttk.Combobox(win, textvariable=sort_dir,
                 values=["По возрастанию","По убыванию"],
                 width=16, state="readonly").grid(row=3, column=2, pady=6, padx=4, sticky="w")

    def run():
        docmap, _ = doctor_map()
        did = docmap.get(doc_var.get())
        sc = {"Фамилия":"p.last_name","Дата госпитализации":"p.admission_date",
              "Диагноз":"dg.name","Статус":"p.discharge_status"
              }.get(sort_var.get(), "p.last_name")
        sd = "DESC" if sort_dir.get() == "По убыванию" else "ASC"
        sql = (
            "SELECT p.last_name||' '||p.first_name||' '||COALESCE(p.middle_name,'') AS fio,"
            " p.birth_date,"
            " DATE_PART('year',AGE(p.birth_date))::INT AS age,"
            " p.insurance_num, p.admission_date, p.discharge_date,"
            " p.discharge_status,"
            " dg.code||' '||dg.name AS diagnosis,"
            " h.name AS hospital, dep.name AS dept "
            "FROM patients p "
            "LEFT JOIN diagnoses   dg  ON dg.id  = p.diagnosis_id "
            "LEFT JOIN departments dep ON dep.id = p.department_id "
            "LEFT JOIN hospitals   h   ON h.id   = p.hospital_id "
            f"WHERE p.doctor_id=%s AND p.admission_date BETWEEN %s AND %s "
            f"ORDER BY {sc} {sd}")
        win.destroy()
        ReportWindow(parent,
            f"Отчёт 1 — {doc_var.get()}  [{d1.get()} – {d2.get()}]",
            sql, (did, d1.get(), d2.get()),
            ["ФИО пациента","Д.р.","Возраст","Полис","Госпитализация",
             "Выписка","Статус","Диагноз","Больница","Отделение"])

    tk.Button(win, text="Сформировать отчёт", width=22, command=run).grid(
        row=4, column=0, columnspan=3, pady=12)
    win.grab_set()


def report_free_doctors(parent):
    win = tk.Toplevel(parent)
    win.title("Отчёт 2 — Врачи с малой нагрузкой")
    win.resizable(False, False)

    tk.Label(win, text="Пациентов не более:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
    max_pat = tk.StringVar(value="2")
    tk.Entry(win, textvariable=max_pat, width=8).grid(row=0, column=1, pady=8, padx=4, sticky="w")

    _, hnames = hospital_map()
    tk.Label(win, text="Больница (оставить пустым = все):").grid(
        row=1, column=0, padx=10, pady=6, sticky="w")
    hosp_var = tk.StringVar(value="")
    ttk.Combobox(win, textvariable=hosp_var, values=[""] + hnames,
                 width=36, state="readonly").grid(row=1, column=1, columnspan=2,
                                                  padx=4, pady=6, sticky="w")
    tk.Label(win, text="Сортировка:").grid(row=2, column=0, padx=10, pady=6, sticky="w")
    sort_var = tk.StringVar(value="Пациентов")
    ttk.Combobox(win, textvariable=sort_var,
                 values=["Фамилия","Должность","Стаж","Больница","Пациентов"],
                 width=20, state="readonly").grid(row=2, column=1, padx=4, pady=6, sticky="w")
    sort_dir = tk.StringVar(value="По возрастанию")
    ttk.Combobox(win, textvariable=sort_dir,
                 values=["По возрастанию","По убыванию"],
                 width=16, state="readonly").grid(row=2, column=2, padx=4, pady=6, sticky="w")

    def run():
        hmap, _ = hospital_map()
        sc = {"Фамилия":"d.last_name","Должность":"p.title",
              "Стаж":"d.hire_date","Больница":"h.name","Пациентов":"d.patient_count"
              }.get(sort_var.get(), "d.patient_count")
        sd = "DESC" if sort_dir.get() == "По убыванию" else "ASC"
        hosp_id = hmap.get(hosp_var.get())
        cond    = "WHERE d.patient_count <= %s"
        params  = [int(max_pat.get() or 2)]
        if hosp_id:
            cond += " AND d.hospital_id=%s"
            params.append(hosp_id)
        sql = (
            "SELECT d.last_name||' '||d.first_name||' '||COALESCE(d.middle_name,'') AS fio,"
            " p.title AS pos, d.cabinet,"
            " DATE_PART('year',AGE(d.hire_date))::INT AS exp,"
            " h.name AS hospital, dep.name AS dept,"
            " d.patient_count AS patients "
            "FROM doctors d "
            "LEFT JOIN positions   p   ON p.id   = d.position_id "
            "LEFT JOIN hospitals   h   ON h.id   = d.hospital_id "
            "LEFT JOIN departments dep ON dep.id = d.department_id "
            f"{cond} ORDER BY {sc} {sd}")
        win.destroy()
        ReportWindow(parent,
            f"Отчёт 2 — Врачи с нагрузкой ≤ {max_pat.get()} пациентов",
            sql, params,
            ["ФИО врача","Должность","Кабинет","Стаж (лет)",
             "Больница","Отделение","Пациентов"])

    tk.Button(win, text="Сформировать отчёт", width=22, command=run).grid(
        row=3, column=0, columnspan=3, pady=12)
    win.grab_set()


def report_department_stats(parent):
    win = tk.Toplevel(parent)
    win.title("Отчёт 3 — Статистика по отделениям")
    win.resizable(False, False)

    tk.Label(win, text="Мин. число пациентов:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
    min_pat = tk.StringVar(value="1")
    tk.Entry(win, textvariable=min_pat, width=8).grid(row=0, column=1, pady=8, padx=4, sticky="w")

    tk.Label(win, text="Сортировка:").grid(row=1, column=0, padx=10, pady=6, sticky="w")
    sort_var = tk.StringVar(value="Пациентов")
    ttk.Combobox(win, textvariable=sort_var,
                 values=["Больница","Отделение","Пациентов","Активных",
                         "Заполненность %","Ср. возраст"],
                 width=22, state="readonly").grid(row=1, column=1, padx=4, pady=6, sticky="w")
    sort_dir = tk.StringVar(value="По убыванию")
    ttk.Combobox(win, textvariable=sort_dir,
                 values=["По возрастанию","По убыванию"],
                 width=16, state="readonly").grid(row=1, column=2, padx=4, pady=6, sticky="w")

    def run():
        sc = {"Больница":"h.name","Отделение":"dep.name",
              "Пациентов":"total","Активных":"active_cnt",
              "Заполненность %":"fill_pct","Ср. возраст":"avg_age"
              }.get(sort_var.get(), "total")
        sd = "DESC" if sort_dir.get() == "По убыванию" else "ASC"
        sql = (
            "SELECT h.name, dep.name,"
            " COUNT(p.id) AS total,"
            " COUNT(CASE WHEN p.discharge_date IS NULL THEN 1 END) AS active_cnt,"
            " ROUND(AVG(DATE_PART('year',AGE(p.birth_date)))::NUMERIC,1) AS avg_age,"
            " COUNT(DISTINCT p.doctor_id) AS doctors,"
            " COUNT(DISTINCT p.diagnosis_id) AS diagnoses,"
            " dep.bed_count,"
            " ROUND(COUNT(p.id)*100.0/NULLIF(dep.bed_count,0),1) AS fill_pct "
            "FROM departments dep "
            "JOIN hospitals h ON h.id=dep.hospital_id "
            "LEFT JOIN patients p ON p.department_id=dep.id "
            "GROUP BY h.name, dep.name, dep.bed_count "
            f"HAVING COUNT(p.id) >= %s ORDER BY {sc} {sd}")
        win.destroy()
        ReportWindow(parent,
            f"Отчёт 3 — Статистика отделений (мин. {min_pat.get()} пациентов)",
            sql, (int(min_pat.get() or 1),),
            ["Больница","Отделение","Всего пациентов","Активных",
             "Ср. возраст","Врачей","Диагнозов","Коек","Заполненность %"])

    tk.Button(win, text="Сформировать отчёт", width=22, command=run).grid(
        row=2, column=0, columnspan=3, pady=12)
    win.grab_set()


class ReportsTab(tk.Frame):
    tab_name = "📊 Отчёты"

    def __init__(self, master, app_ref):
        super().__init__(master)
        self.app = app_ref
        self._build_ui()

    def _build_ui(self):
        outer = tk.Frame(self, padx=30, pady=30)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Отчёты", font=("", 14, "bold")).pack(anchor="w", pady=(0, 16))

        reports = [
            ("Пациенты выбранного врача за период",
             "Список всех пациентов конкретного врача\nс фильтром по датам госпитализации",
             lambda: report_patients_by_doctor(self.app)),
            ("Врачи с малой нагрузкой",
             "Врачи, у которых число активных пациентов\nне превышает заданный порог",
             lambda: report_free_doctors(self.app)),
            ("Статистика по отделениям",
             "Заполненность, средний возраст,\nчисло диагнозов и врачей по каждому отделению",
             lambda: report_department_stats(self.app)),
        ]

        for title, desc, cmd in reports:
            card = tk.Frame(outer, relief="groove", bd=1, padx=16, pady=12)
            card.pack(fill="x", pady=6)
            left = tk.Frame(card)
            left.pack(side="left", fill="both", expand=True)
            tk.Label(left, text=title, font=("", 11, "bold"),
                     anchor="w").pack(anchor="w")
            tk.Label(left, text=desc, fg="gray", anchor="w",
                     justify="left").pack(anchor="w", pady=(4, 0))
            tk.Button(card, text="Открыть", width=12,
                      command=cmd).pack(side="right", padx=4)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Медицинская информационная система — г. Ижевск")
        self.geometry("1280x720")
        self.minsize(900, 560)

        self.config(menu=tk.Menu(self)) 

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tab_classes = [HospitalsTab, DepartmentsTab, PositionsTab,
                       DiagnosesTab, DoctorsTab, PatientsTab]
        for Cls in tab_classes:
            tab = Cls(nb)
            nb.add(tab, text=f"  {Cls.tab_name}  ")

        reports_tab = ReportsTab(nb, self)
        nb.add(reports_tab, text=f"  {ReportsTab.tab_name}  ")

        style = ttk.Style()
        style.configure("TNotebook.Tab", padding=[8, 4])

        self.status = tk.StringVar(value="Готово")
        tk.Label(self, textvariable=self.status, anchor="w",
                 relief="sunken", bd=1).pack(fill="x", side="bottom")
        self._check_connection()

    def _check_connection(self):
        try:
            conn().close()
            self.status.set(
                "Подключено к PostgreSQL  |  База: медицинская система — г. Ижевск")
        except Exception as e:
            messagebox.showerror(
                "Ошибка подключения",
                f"Не удалось подключиться к PostgreSQL:\n{e}\n\n"
                "Проверьте параметры DB в начале файла.")
            self.status.set("Нет подключения к БД")


if __name__ == "__main__":
    App().mainloop()
