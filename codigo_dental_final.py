# -*- coding: utf-8 -*-
"""
DentalClinicApp - Single-file Tkinter + SQLite application
Requisitos: Python 3.x (incluye tkinter y sqlite3 por defecto)
Ejecución: python dental_clinic_app.py
Descripción:
- ABM de pacientes (alta, baja, modificación) + buscador por nombre/apellido/DNI
- Agenda de turnos por fecha (hora, paciente, motivo)
- Historia clínica resumida (alergias, medicamentos, antecedentes)
- Tratamientos (lista cronológica con fecha/descripción/observaciones)
- Odontograma interactivo (adulto y temporal): click en pieza/cara para cambiar estado (código de colores)
- Periodoncia: registro de PS, MG, NI, SS, SUP, MOV por pieza/sitio
- Crea y migra la base SQLite automáticamente si no existe
- Archivo único, con comentarios para facilitar mantenimiento
NOTA: Esta es una implementación didáctica y compacta que cumple los requisitos básicos
y puede ampliarse según necesidades reales del consultorio.
"""
import sqlite3
import json
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
DB_PATH = "consultorio.db"
###############################################
# Utilidades y Persistencia (SQLite + Helpers)
###############################################
def get_conn():
    """Retorna una conexión a la base de datos."""
    return sqlite3.connect(DB_PATH)
def init_db():
    """Crea tablas si no existen y aplica pequeñas migraciones no destructivas."""
    with get_conn() as con:
        cur = con.cursor()
        # Pacientes
        cur.execute("""
        CREATE TABLE IF NOT EXISTS patients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT UNIQUE,
            nombre TEXT,
            apellido TEXT,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            fecha_nacimiento TEXT
        )""")
        # Historia clínica simple
        cur.execute("""
        CREATE TABLE IF NOT EXISTS history(
            patient_id INTEGER UNIQUE,
            data_json TEXT,  -- Almacena todo el formulario en formato JSON
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )""")
        # Turnos
        cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,   -- YYYY-MM-DD
            hora TEXT,   -- HH:MM
            patient_id INTEGER,
            motivo TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE SET NULL
        )""")
        # Tratamientos
        cur.execute("""
        CREATE TABLE IF NOT EXISTS treatments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            fecha TEXT,      -- YYYY-MM-DD
            descripcion TEXT,
            observaciones TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )""")
        # Odontograma (por paciente: mapa estados por pieza y cara)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS odontogram(
            patient_id INTEGER PRIMARY KEY,
            esquema TEXT,      -- 'adulto' o 'temporal'
            data_json TEXT,      -- { "11":{"O":"Sano","M":"Caries",...}, ... }
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )""")
        # Periodoncia: valores por paciente + pieza + sitio
        cur.execute("""
        CREATE TABLE IF NOT EXISTS periodontics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            pieza TEXT,            -- 11..48 (adulto) o 51..85 (temporal), etc.
            sitio TEXT,            -- Mesial, Distal, etc. (se usan nombres completos)
            ps REAL,               -- Profundidad de sondaje (mm)
            mg REAL,               -- Margen gingival (mm)
            ni REAL,               -- Nivel de inserción (mm) = ps - mg si se desea
            ss INTEGER,            -- Sangrado (0/1)
            sup INTEGER,           -- Supuración (0/1)
            mov INTEGER,           -- Movilidad (0..3)
            UNIQUE(patient_id, pieza, sitio),
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )""")
        con.commit()
###############################################
# Componentes de UI reutilizables
###############################################
class SearchBar(ttk.Frame):
    def __init__(self, master, on_search, placeholder="Buscar..."):
        super().__init__(master)
        self.on_search = on_search
        self.var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.var, width=40)
        entry.pack(side=tk.LEFT, padx=(0,6))
        entry.insert(0, placeholder)
        def _focus_in(e):
            if self.var.get() == placeholder:
                self.var.set("")
        def _focus_out(e):
            if self.var.get().strip() == "":
                self.var.set(placeholder)
        entry.bind("<FocusIn>", _focus_in)
        entry.bind("<FocusOut>", _focus_out)
        entry.bind("<KeyRelease>", lambda e: self.on_search(self.text()))
        ttk.Button(self, text="Buscar", command=lambda: self.on_search(self.text())).pack(side=tk.LEFT)
        ttk.Button(self, text="Limpiar", command=self._clear).pack(side=tk.LEFT, padx=(6,0))
    def text(self):
        t = self.var.get()
        if t.startswith("Buscar"): return ""
        return t.strip()
    def _clear(self):
        self.var.set("")
        self.on_search("")
###############################################
# Pestaña Pacientes (ABM + Buscador)
###############################################
class PatientsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.selected_id = None
        # Buscador
        self.search = SearchBar(self, self.search_patients, "Buscar: nombre, apellido o DNI")
        self.search.pack(fill=tk.X, pady=8)
        # Lista + Formulario
        container = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        container.pack(fill=tk.BOTH, expand=True)
        # Listado
        left = ttk.Frame(container)
        self.tree = ttk.Treeview(left, columns=("dni","nombre","apellido","telefono"), show="headings", height=16)
        for col, txt, w in [("dni","DNI",110),("nombre","Nombre",140),("apellido","Apellido",140),("telefono","Teléfono",110)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        # Botones listado
        btns = ttk.Frame(left)
        ttk.Button(btns, text="Nuevo", command=self.new_patient).pack(side=tk.LEFT, padx=4, pady=6)
        ttk.Button(btns, text="Eliminar", command=self.delete_patient).pack(side=tk.LEFT, padx=4)
        btns.pack(fill=tk.X)
        container.add(left, weight=1)
        # Formulario
        right = ttk.Frame(container, padding=10)
        self.vars = {k: tk.StringVar() for k in [
            "dni","nombre","apellido","telefono","email","direccion","fecha_nacimiento"
        ]}
        row = 0
        for label, key in [("DNI","dni"),("Nombre","nombre"),("Apellido","apellido"),
                            ("Teléfono","telefono"),("Email","email"),
                            ("Dirección","direccion"),("Fecha Nac. (YYYY-MM-DD)","fecha_nacimiento")]:
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(right, textvariable=self.vars[key], width=35)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            if key in ["dni", "telefono"]:
                vcmd = (self.register(self.validate_numeric), '%P')
                entry.config(validate="key", validatecommand=vcmd)
            row += 1
        right.columnconfigure(1, weight=1)
        # Botones form
        frm_btns = ttk.Frame(right)
        ttk.Button(frm_btns, text="Guardar / Actualizar", command=self.save_patient).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_btns, text="Limpiar", command=self.clear_form).pack(side=tk.LEFT, padx=4)
        frm_btns.grid(row=row, column=0, columnspan=2, pady=10)
        container.add(right, weight=1)
        self.refresh_list()
    def validate_numeric(self, text):
        return text.isdigit() or text == ""
    def search_patients(self, q):
        with get_conn() as con:
            c = con.cursor()
            q = f"%{q}%"
            c.execute("""SELECT id,dni,nombre,apellido,telefono
                              FROM patients
                              WHERE dni LIKE ? OR nombre LIKE ? OR apellido LIKE ?
                              ORDER BY apellido,nombre""",(q,q,q))
            rows = c.fetchall()
            self.tree.delete(*self.tree.get_children())
            for rid, dni, nom, ape, tel in rows:
                self.tree.insert("", "end", iid=str(rid), values=(dni,nom,ape,tel))
    def refresh_list(self):
        self.search_patients("")
    def on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            self.selected_id = None
            return
        self.selected_id = int(sel[0])
        with get_conn() as con:
            c = con.cursor()
            c.execute("SELECT dni,nombre,apellido,telefono,email,direccion,fecha_nacimiento FROM patients WHERE id=?",
                      (self.selected_id,))
            row = c.fetchone()
            if row:
                for key, val in zip(self.vars.keys(), row):
                    self.vars[key].set("" if val is None else str(val))
        self.app.on_patient_change(self.selected_id)
    def new_patient(self):
        self.selected_id = None
        self.clear_form()
    def clear_form(self):
        for v in self.vars.values():
            v.set("")
    def save_patient(self):
        data = {k:v.get().strip() for k,v in self.vars.items()}
        if not data["dni"] or not data["nombre"] or not data["apellido"]:
            messagebox.showwarning("Campos requeridos", "Complete DNI, Nombre y Apellido.")
            return
        # Validar formato de fecha
        if data["fecha_nacimiento"]:
            try:
                datetime.strptime(data["fecha_nacimiento"], '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error de fecha", "Formato de fecha de nacimiento inválido. Use YYYY-MM-DD.")
                return
        with get_conn() as con:
            c = con.cursor()
            try:
                if self.selected_id is None:
                    c.execute("""INSERT INTO patients(dni,nombre,apellido,telefono,email,direccion,fecha_nacimiento)
                                     VALUES(?,?,?,?,?,?,?)""",
                                     (data["dni"],data["nombre"],data["apellido"],data["telefono"],
                                     data["email"],data["direccion"],data["fecha_nacimiento"]))
                    self.selected_id = c.lastrowid
                    # Crear historia vacía
                    c.execute("""INSERT OR IGNORE INTO history(patient_id, data_json)
                                     VALUES(?,?)""",(self.selected_id, "{}"))
                else:
                    c.execute("""UPDATE patients SET dni=?,nombre=?,apellido=?,telefono=?,email=?,direccion=?,fecha_nacimiento=?
                                     WHERE id=?""",
                                     (data["dni"],data["nombre"],data["apellido"],data["telefono"],
                                     data["email"],data["direccion"],data["fecha_nacimiento"], self.selected_id))
                con.commit()
                messagebox.showinfo("Éxito", "Paciente guardado correctamente.")
                self.refresh_list()
                if self.selected_id:
                    self.tree.selection_set(str(self.selected_id))
            except sqlite3.IntegrityError as e:
                messagebox.showerror("Error", f"El DNI ya existe u otro error de integridad.\n{e}")
    def delete_patient(self):
        sel = self.tree.selection()
        if not sel: return
        pid = int(sel[0])
        if not messagebox.askyesno("Eliminar", "¿Eliminar paciente y todos sus registros asociados?"):
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("DELETE FROM patients WHERE id=?", (pid,))
            con.commit()
            self.selected_id = None
            self.refresh_list()
            self.clear_form()
            self.app.on_patient_change(None)
###############################################
# Pestaña Historia Clínica
###############################################
class HistoryTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.patient_id = None
        self.form_vars = {}
        self.create_form()

    def create_form(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(container, borderwidth=0, background="#f0f0f0")
        form_frame = ttk.Frame(canvas, padding=10)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        form_frame.columnconfigure(1, weight=1)
        row_counter = 0

        def add_section_title(text):
            nonlocal row_counter
            ttk.Label(form_frame, text=text, font=("TkDefaultFont", 11, "bold")).grid(row=row_counter, column=0, columnspan=2, sticky="w", pady=(15, 5))
            row_counter += 1

        def add_text_area(label_text, key, height=4):
            nonlocal row_counter
            ttk.Label(form_frame, text=label_text).grid(row=row_counter, column=0, columnspan=2, sticky="w", pady=(5, 2))
            widget = tk.Text(form_frame, height=height, width=80, wrap="word")
            widget.grid(row=row_counter+1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 5))
            self.form_vars[key] = widget
            row_counter += 2

        def add_yes_no_question(label_text, key_prefix):
            nonlocal row_counter
            ttk.Label(form_frame, text=label_text).grid(row=row_counter, column=0, sticky="w", pady=(5,2))
            frame_buttons = ttk.Frame(form_frame)
            frame_buttons.grid(row=row_counter, column=1, sticky="w")
            
            var = tk.StringVar(value="No")
            self.form_vars[f"{key_prefix}_respuesta"] = var
            
            ttk.Radiobutton(frame_buttons, text="Sí", variable=var, value="Sí").pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(frame_buttons, text="No", variable=var, value="No").pack(side=tk.LEFT, padx=5)
            
            row_counter += 1
            ttk.Label(form_frame, text="Observaciones:").grid(row=row_counter, column=0, sticky="w", pady=2)
            obs_var = tk.StringVar()
            self.form_vars[f"{key_prefix}_observaciones"] = obs_var
            ttk.Entry(form_frame, textvariable=obs_var, width=80).grid(row=row_counter, column=1, sticky="ew", padx=4)
            row_counter += 1

        add_section_title("Historia clínica general")
        add_text_area("Motivo de la consulta:", "motivo_consulta")
        
        # --- Preguntas de "Sí/No" actualizadas ---
        add_yes_no_question("Tuvo transfusiones?", "transfusiones")
        add_yes_no_question("Fue operado alguna vez?", "operacion")
        add_yes_no_question("Fuma?", "fuma")
        add_yes_no_question("Está embarazada?", "embarazo")
        add_yes_no_question("Sufre de alguna enfermedad?", "enfermedad")
        add_yes_no_question("Tiene algún problema respiratorio?", "problema_respiratorio")
        add_yes_no_question("Hace algún tratamiento médico?", "tratamiento_medico")
        add_yes_no_question("Es alérgico a alguna droga?", "alergia_droga")
        add_yes_no_question("Toma seguido aspirina y/o anticoagulante?", "aspirina_anticoagulante")
        add_yes_no_question("Tiene presión alta?", "presion_alta")
        add_yes_no_question("Chagas?", "chagas")
        add_yes_no_question("Tiene problemas renales?", "problemas_renales")
        add_yes_no_question("Ulcera Gástrica?", "ulcera_gastrica")
        add_yes_no_question("Tuvo hepatitis?", "hepatitis")
        add_yes_no_question("Tiene algún problema hepático?", "problema_hepatico")
        add_yes_no_question("Tuvo convulsiones?", "convulsiones")
        add_yes_no_question("Es epiléptico?", "epileptico")
        add_yes_no_question("Ha tenido Sífilis o Gonorrea?", "sifilis_gonorrea")
        # ----------------------------------------
        
        ttk.Button(form_frame, text="Guardar Historia Clínica", command=self.save).grid(row=row_counter, column=0, columnspan=2, pady=15)

    def set_patient(self, pid):
        self.patient_id = pid
        self.clear_form()
        if not pid: return
        try:
            with get_conn() as con:
                c = con.cursor()
                c.execute("SELECT data_json FROM history WHERE patient_id=?", (pid,))
                row = c.fetchone()
                if row and row[0]:
                    try:
                        data = json.loads(row[0])
                        for key, var in self.form_vars.items():
                            if key in data:
                                if isinstance(var, tk.StringVar):
                                    var.set(data[key])
                                elif isinstance(var, tk.Text):
                                    var.delete("1.0", tk.END)
                                    var.insert("1.0", data[key])
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Error al cargar la historia clínica. El formato es inválido.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al cargar los datos: {e}")

    def clear_form(self):
        for var in self.form_vars.values():
            if isinstance(var, tk.StringVar):
                var.set("No")
            elif isinstance(var, tk.Text):
                var.delete("1.0", tk.END)

    def save(self):
        if not self.patient_id:
            messagebox.showwarning("Sin paciente", "Seleccione un paciente.")
            return
        data = {}
        for key, var in self.form_vars.items():
            if isinstance(var, tk.StringVar):
                data[key] = var.get()
            elif isinstance(var, tk.Text):
                data[key] = var.get("1.0", tk.END).strip()
        data_json = json.dumps(data)
        
        try:
            with get_conn() as con:
                c = con.cursor()
                c.execute("""
                    INSERT INTO history(patient_id, data_json) VALUES(?,?)
                    ON CONFLICT(patient_id) DO UPDATE SET data_json=excluded.data_json
                """, (self.patient_id, data_json))
                con.commit()
                messagebox.showinfo("Guardado", "Historia clínica actualizada.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al guardar los datos: {e}")
###############################################
# Pestaña Tratamientos
##############################################
class TreatmentsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.patient_id = None
        top = ttk.Frame(self)
        ttk.Label(top, text="Fecha (YYYY-MM-DD):").pack(side=tk.LEFT, padx=4)
        self.var_fecha = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(top, textvariable=self.var_fecha, width=12).pack(side=tk.LEFT)
        ttk.Label(top, text="Descripción:").pack(side=tk.LEFT, padx=4)
        self.var_desc = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_desc, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(top, text="Obs.:").pack(side=tk.LEFT, padx=4)
        self.var_obs = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_obs, width=30).pack(side=tk.LEFT)
        ttk.Button(top, text="Agregar", command=self.add).pack(side=tk.LEFT, padx=6)
        top.pack(fill=tk.X, pady=6)
        self.tree = ttk.Treeview(self, columns=("fecha","desc","obs"), show="headings")
        self.tree.heading("fecha", text="Fecha")
        self.tree.heading("desc", text="Descripción")
        self.tree.heading("obs", text="Observaciones")
        self.tree.column("fecha", width=90)
        self.tree.column("desc", width=420)
        self.tree.column("obs", width=260)
        self.tree.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(self)
        ttk.Button(btns, text="Eliminar seleccionado", command=self.delete).pack(side=tk.LEFT, padx=4, pady=6)
        btns.pack(fill=tk.X)
    def set_patient(self, pid):
        self.patient_id = pid
        self.refresh()
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if not self.patient_id: return
        with get_conn() as con:
            c = con.cursor()
            c.execute("""SELECT id, fecha, descripcion, observaciones
                              FROM treatments WHERE patient_id=? ORDER BY fecha ASC, id ASC""",(self.patient_id,))
            for tid, f, d, o in c.fetchall():
                self.tree.insert("", "end", iid=str(tid), values=(f or "", d or "", o or ""))
    def add(self):
        if not self.patient_id:
            messagebox.showwarning("Sin paciente", "Seleccione un paciente.")
            return
        fecha = self.var_fecha.get().strip()
        desc = self.var_desc.get().strip()
        obs = self.var_obs.get().strip()
        if not fecha or not desc:
            messagebox.showwarning("Campos requeridos", "Complete Fecha y Descripción.")
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("""INSERT INTO treatments(patient_id, fecha, descripcion, observaciones)
                              VALUES(?,?,?,?)""",(self.patient_id, fecha, desc, obs))
            con.commit()
            self.var_desc.set(""); self.var_obs.set("")
            self.refresh()
    def delete(self):
        sel = self.tree.selection()
        if not sel: return
        tid = int(sel[0])
        if not messagebox.askyesno("Eliminar", "¿Eliminar tratamiento seleccionado?"):
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("DELETE FROM treatments WHERE id=?", (tid,))
            con.commit()
            self.refresh()
###############################################
# Pestaña Agenda (Turnos)
###############################################
class AppointmentsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        top = ttk.Frame(self)
        ttk.Label(top, text="Fecha (YYYY-MM-DD):").pack(side=tk.LEFT, padx=4)
        self.var_fecha = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(top, textvariable=self.var_fecha, width=12).pack(side=tk.LEFT)
        ttk.Label(top, text="Hora (HH:MM):").pack(side=tk.LEFT, padx=4)
        self.var_hora = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        ttk.Entry(top, textvariable=self.var_hora, width=8).pack(side=tk.LEFT)
        ttk.Label(top, text="Paciente (ID):").pack(side=tk.LEFT, padx=4)
        self.var_pid = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_pid, width=6).pack(side=tk.LEFT)
        ttk.Label(top, text="Motivo:").pack(side=tk.LEFT, padx=4)
        self.var_motivo = tk.StringVar()
        ttk.Entry(top, textvariable=self.var_motivo, width=32).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(top, text="Agregar turno", command=self.add).pack(side=tk.LEFT, padx=6)
        top.pack(fill=tk.X, pady=6)
        self.filter_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        filter_frame = ttk.Frame(self)
        ttk.Label(filter_frame, text="Ver turnos del día (YYYY-MM-DD):").pack(side=tk.LEFT, padx=4)
        ttk.Entry(filter_frame, textvariable=self.filter_date, width=12).pack(side=tk.LEFT)
        ttk.Button(filter_frame, text="Filtrar", command=self.refresh).pack(side=tk.LEFT, padx=6)
        filter_frame.pack(fill=tk.X)
        self.tree = ttk.Treeview(self, columns=("hora","paciente","motivo","pid"), show="headings")
        for col, txt, w in [("hora","Hora",80),("paciente","Paciente",240),("motivo","Motivo",360),("pid","ID",60)]:
            self.tree.heading(col, text=txt); self.tree.column(col, width=w, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(self)
        ttk.Button(btns, text="Eliminar", command=self.delete).pack(side=tk.LEFT, padx=4, pady=6)
        btns.pack(fill=tk.X)
    def add(self):
        fecha = self.var_fecha.get().strip()
        hora = self.var_hora.get().strip()
        motivo = self.var_motivo.get().strip()
        pid = self.var_pid.get().strip()
        if not (fecha and hora and pid):
            messagebox.showwarning("Campos requeridos", "Complete Fecha, Hora y Paciente (ID).")
            return
        try:
            pid = int(pid)
        except:
            messagebox.showerror("ID inválido", "Paciente (ID) debe ser un número entero.")
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("SELECT nombre, apellido FROM patients WHERE id=?", (pid,))
            if not c.fetchone():
                messagebox.showerror("Paciente", "No existe un paciente con ese ID.")
                return
            c.execute("""INSERT INTO appointments(fecha,hora,patient_id,motivo) VALUES(?,?,?,?)""",
                      (fecha,hora,pid,motivo))
            con.commit()
            self.refresh()
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        fecha = self.filter_date.get().strip()
        with get_conn() as con:
            c = con.cursor()
            c.execute("""
                SELECT a.id, a.hora, p.apellido || ', ' || p.nombre AS nom, a.motivo, a.patient_id
                FROM appointments a
                LEFT JOIN patients p ON p.id = a.patient_id
                WHERE a.fecha=?
                ORDER BY a.hora ASC, a.id ASC
            """, (fecha,))
            for aid, h, nom, mot, pid in c.fetchall():
                self.tree.insert("", "end", iid=str(aid), values=(h or "", nom or "-", mot or "", pid or ""))
    def delete(self):
        sel = self.tree.selection()
        if not sel: return
        aid = int(sel[0])
        if not messagebox.askyesno("Eliminar", "¿Eliminar turno seleccionado?"):
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("DELETE FROM appointments WHERE id=?", (aid,))
            con.commit()
            self.refresh()
###############################################
# Pestaña Odontograma (Canvas interactivo)
###############################################
ODONTO_STATES = ["Sano","Caries","Restauración","Ausente","Implante"]
ODONTO_COLORS = {
    "Sano": "#A7F3D0",        # verde suave
    "Caries": "#FCA5A5",       # rojo suave
    "Restauración": "#93C5FD",# azul
    "Ausente": "#E5E7EB",      # gris
    "Implante": "#FDE68A",     # amarillo
}
# caras estándar: Oclusal/Incisal (O/I), Mesial(M), Distal(D), Vestibular(B), Lingual/Palatina(L)
SURFACES = ["O","M","D","B","L"]
# Piezas por esquema FDI
ADULTO_PIEZAS = [str(n) for n in (
    list(range(18,10,-1)) + list(range(21,29)) + list(range(48,40,-1)) + list(range(31,39))
)]
# Temporal (dentición primaria): 55..51, 61..65, 85..81, 71..75
TEMPORAL_PIEZAS = [str(n) for n in (list(range(55,50,-1))+list(range(61,66))+list(range(85,80,-1))+list(range(71,76)))]
class OdontogramTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.patient_id = None
        self.esquema = tk.StringVar(value="adulto")
        top = ttk.Frame(self)
        ttk.Radiobutton(top, text="Dentición permanente", variable=self.esquema, value="adulto", command=self._reload).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(top, text="Dentición temporal", variable=self.esquema, value="temporal", command=self._reload).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Guardar odontograma", command=self.save).pack(side=tk.RIGHT, padx=6)
        top.pack(fill=tk.X, pady=6)
        self.canvas = tk.Canvas(self, bg="white", height=380)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        # Leyenda
        legend = ttk.Frame(self)
        for st in ODONTO_STATES:
            sw = tk.Canvas(legend, width=18, height=18, highlightthickness=1, highlightbackground="#999")
            sw.create_rectangle(2,2,16,16, fill=ODONTO_COLORS[st], outline="")
            sw.pack(side=tk.LEFT, padx=(8,2), pady=6)
            ttk.Label(legend, text=st).pack(side=tk.LEFT)
        legend.pack()
        self.data = {}    # {pieza: {cara: estado}}
        self.rect_index = {}  # mapea item_id -> (pieza, cara)
        self._draw()
    def set_patient(self, pid):
        self.patient_id = pid
        self.load()
    def _grid_piezas(self):
        return ADULTO_PIEZAS if self.esquema.get()=="adulto" else TEMPORAL_PIEZAS
    def _draw(self):
        self.canvas.delete("all")
        self.rect_index.clear()
        piezas = self._grid_piezas()
        # 16 arriba (8+8) y 16 abajo (8+8) aprox
        margin = 12
        cell_w = 40
        cell_h = 28
        gap = 10
        def draw_row(piezas_row, y0):
            for i, pieza in enumerate(piezas_row):
                x0 = margin + i*(cell_w+gap)
                # 5 caras en cruz simple
                # centro = O/I, arriba = B, abajo = L, izq=M, der=D
                cx, cy = x0+cell_w//2, y0+cell_h//2
                blocks = {
                    "O": (x0+cell_w//4, y0+cell_h//4, x0+3*cell_w//4, y0+3*cell_h//4),
                    "B": (x0+cell_w//4, y0, x0+3*cell_w//4, y0+cell_h//4),
                    "L": (x0+cell_w//4, y0+3*cell_h//4, x0+3*cell_w//4, y0+cell_h),
                    "M": (x0, y0+cell_h//4, x0+cell_w//4, y0+3*cell_h//4),
                    "D": (x0+3*cell_w//4, y0+cell_h//4, x0+cell_w, y0+3*cell_h//4),
                }
                # etiqueta pieza
                self.canvas.create_text(x0+cell_w//2, y0-8, text=pieza, font=("TkDefaultFont", 9))
                for cara in SURFACES:
                    x1,y1,x2,y2 = blocks[cara]
                    estado = self.data.get(pieza, {}).get(cara, "Sano")
                    fill = ODONTO_COLORS.get(estado, "#FFF")
                    rect = self.canvas.create_rectangle(x1,y1,x2,y2, fill=fill, outline="#333")
                    self.rect_index[rect] = (pieza, cara)
        # Partimos lista en 2 filas de 16
        row1 = piezas[:16]
        row2 = piezas[16:]
        draw_row(row1, 30)
        draw_row(row2, 180)
    def on_click(self, event):
        if not self.patient_id:
            messagebox.showwarning("Sin paciente", "Seleccione un paciente para editar el odontograma.")
            return
        item = self.canvas.find_closest(event.x, event.y)[0]
        if item in self.rect_index:
            pieza, cara = self.rect_index[item]
            current_state = self.data.get(pieza, {}).get(cara, "Sano")
            current_idx = ODONTO_STATES.index(current_state)
            next_idx = (current_idx + 1) % len(ODONTO_STATES)
            next_state = ODONTO_STATES[next_idx]
            
            # Actualizar el diccionario de datos
            if pieza not in self.data:
                self.data[pieza] = {}
            self.data[pieza][cara] = next_state
            
            # Actualizar el color del rectángulo en el canvas
            self.canvas.itemconfig(item, fill=ODONTO_COLORS[next_state])
    def save(self):
        if not self.patient_id:
            messagebox.showwarning("Sin paciente", "Seleccione un paciente.")
            return
        data_json = json.dumps(self.data)
        esquema = self.esquema.get()
        with get_conn() as con:
            c = con.cursor()
            c.execute("""
                INSERT INTO odontogram(patient_id, esquema, data_json) VALUES(?,?,?)
                ON CONFLICT(patient_id) DO UPDATE SET esquema=excluded.esquema, data_json=excluded.data_json
            """, (self.patient_id, esquema, data_json))
            con.commit()
            messagebox.showinfo("Guardado", "Odontograma actualizado.")
    def load(self):
        self.data.clear()
        if not self.patient_id: return
        with get_conn() as con:
            c = con.cursor()
            c.execute("SELECT esquema, data_json FROM odontogram WHERE patient_id=?", (self.patient_id,))
            row = c.fetchone()
            if row:
                esquema, data_json = row
                self.esquema.set(esquema)
                self.data = json.loads(data_json)
        self._draw()
    def _reload(self):
        self.load()
###############################################
# Pestaña Periodoncia
###############################################
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json

# Asume que estas variables y funciones están definidas en otro lugar
# ADULTO_PIEZAS = [...]
# get_conn = [...]

class PeriodonticsTab(ttk.Frame):
    """
    Pestaña Periodoncia reorganizada en 4 divisiones con etiquetas al costado.
    Compatible con la tabla `periodontics` de la DB.
    """
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.patient_id = None
        self.sitios = ["MB", "B", "DB", "ML", "L", "DL"]  # 6 sitios estándar
        self.widgets = {}

        # Asume que ADULTO_PIEZAS está definida en tu código
        ADULTO_PIEZAS = [
            "18", "17", "16", "15", "14", "13", "12", "11",
            "21", "22", "23", "24", "25", "26", "27", "28",
            "48", "47", "46", "45", "44", "43", "42", "41",
            "31", "32", "33", "34", "35", "36", "37", "38"
        ]
        
        piezas = ADULTO_PIEZAS[:]
        top = piezas[:16]  # 18..11 + 21..28 (fila superior)
        bot = piezas[16:]  # 48..41 + 31..38 (fila inferior)

        top_left, top_right = top[:8], top[8:]
        bot_left, bot_right = bot[:8], bot[8:]

        self._build_ui(top_left, top_right, bot_left, bot_right)
        self.set_patient(None)

    # ---------------- UI helpers ----------------
    def _make_scrollable_frame(self, parent):
        """Frame con scroll horizontal (vertical auto)."""
        container = ttk.Frame(parent)
        canvas = tk.Canvas(container, highlightthickness=0, height=220)
        hscroll = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=hscroll.set)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_config)

        canvas.pack(side=tk.TOP, fill="both", expand=True)
        hscroll.pack(side=tk.TOP, fill="x")
        container.pack(fill=tk.BOTH, expand=True)
        return inner

    def _build_tooth_column(self, parent, pieza):
        """Crea los widgets por pieza (columna)."""
        col = ttk.Frame(parent, borderwidth=1, relief=tk.GROOVE, padding=4)
        col.pack(side=tk.LEFT, padx=3, pady=4)

        ttk.Label(col, text=pieza, font=("TkDefaultFont", 9, "bold")).pack()

        ps_vars, ni_vars, ss_vars, sup_vars = [], [], [], []

        # PS
        row_ps = ttk.Frame(col); row_ps.pack(pady=(4,2))
        for i in range(6):
            v = tk.StringVar(value="0")
            ttk.Entry(row_ps, textvariable=v, width=3).pack(side=tk.LEFT, padx=1)
            ps_vars.append(v)

        # MG
        mg_var = tk.StringVar(value="0")
        ttk.Label(col, text="MG").pack()
        ttk.Entry(col, textvariable=mg_var, width=5).pack(pady=(0,4))

        # NI
        row_ni = ttk.Frame(col); row_ni.pack(pady=(2,2))
        for i in range(6):
            v = tk.StringVar(value="N/A")
            ttk.Entry(row_ni, textvariable=v, width=3).pack(side=tk.LEFT, padx=1)
            ni_vars.append(v)

        # SS
        row_ss = ttk.Frame(col); row_ss.pack(pady=(2,2))
        for i in range(6):
            v = tk.IntVar(value=0)
            ttk.Checkbutton(row_ss, variable=v).pack(side=tk.LEFT)
            ss_vars.append(v)

        # SUP
        row_sup = ttk.Frame(col); row_sup.pack(pady=(2,2))
        for i in range(6):
            v = tk.IntVar(value=0)
            ttk.Checkbutton(row_sup, variable=v).pack(side=tk.LEFT)
            sup_vars.append(v)

        # MOV
        ttk.Label(col, text="MOV").pack()
        mov_var = tk.StringVar(value="0")
        ttk.Entry(col, textvariable=mov_var, width=4).pack(pady=(0,6))

        # Nota
        ttk.Label(col, text="Nota").pack()
        nota_var = tk.StringVar(value="")
        ttk.Entry(col, textvariable=nota_var, width=10).pack(pady=(0,4))

        return pieza, {
            "ps": ps_vars, "mg": mg_var, "ni": ni_vars,
            "ss": ss_vars, "sup": sup_vars, "mov": mov_var, "nota": nota_var
        }

    def _build_section(self, parent, title, piezas):
        """Sección con etiquetas fijas a la izquierda y dientes a la derecha."""
        lf = ttk.LabelFrame(parent, text=title, padding=6)
        lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        # columna de etiquetas
        labels_frame = ttk.Frame(lf)
        labels_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,8))
        for text in [
            "Prof. Sondaje",
            "Margen Gingival",
            "Nivel Inserción",
            "Supuración",
            "Sangrado",
            "Movilidad",
            "Nota"
        ]:
            ttk.Label(labels_frame, text=text, anchor="w").pack(fill=tk.X, pady=2)

        # frame con dientes
        inner = self._make_scrollable_frame(lf)
        for pieza in piezas:
            p, wd = self._build_tooth_column(inner, pieza)
            self.widgets[p] = wd

    # ---------------- Construcción UI principal ----------------
    def _build_ui(self, top_left, top_right, bot_left, bot_right):
        container = ttk.Frame(self, padding=6)
        container.pack(fill=tk.BOTH, expand=True)

        # fila superior
        top_row = ttk.Frame(container); top_row.pack(fill=tk.X, pady=4)
        self._build_section(top_row, "Vestibular (Superior)", top_left)
        self._build_section(top_row, "Palatino (Superior)", top_right)

        # fila inferior
        bot_row = ttk.Frame(container); bot_row.pack(fill=tk.X, pady=4)
        self._build_section(bot_row, "Lingual (Inferior)", bot_left)
        self._build_section(bot_row, "Vestibular (Inferior)", bot_right)

        # Panel inferior con métricas
        bottom = ttk.Frame(self, padding=6)
        bottom.pack(fill=tk.X, pady=(6,0))

        self.profundidad_media_var = tk.StringVar()
        self.nivel_insercion_var = tk.StringVar()
        self.porcentaje_sas_var = tk.StringVar()
        self.porcentaje_placa_var = tk.StringVar()

        ttk.Label(bottom, text="Prof. media =").pack(side=tk.LEFT, padx=2)
        ttk.Entry(bottom, textvariable=self.profundidad_media_var, width=8).pack(side=tk.LEFT)
        ttk.Label(bottom, text="Nivel inserción medio =").pack(side=tk.LEFT, padx=6)
        ttk.Entry(bottom, textvariable=self.nivel_insercion_var, width=8).pack(side=tk.LEFT)
        ttk.Label(bottom, text="% SAS =").pack(side=tk.LEFT, padx=6)
        ttk.Entry(bottom, textvariable=self.porcentaje_sas_var, width=8).pack(side=tk.LEFT)
        ttk.Label(bottom, text="% Placa =").pack(side=tk.LEFT, padx=6)
        ttk.Entry(bottom, textvariable=self.porcentaje_placa_var, width=8).pack(side=tk.LEFT)

        # Botones
        btns = ttk.Frame(self, padding=6)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Guardar en DB", command=self.save_all_to_db).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cargar último", command=self.refresh).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Calcular", command=self.calculate_metrics).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Limpiar", command=self.clear_form).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Importar", command=self.import_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Exportar", command=self.export_file).pack(side=tk.LEFT, padx=4)

    # ---------------- Funciones principales (DB + métricas) ----------------
    def set_patient(self, pid):
        self.patient_id = pid
        self.clear_form()
        if pid:
            self.refresh()

    def refresh(self):
        """Carga los datos desde DB para el paciente actual"""
        self.clear_form(keep_zero=True)
        if not self.patient_id:
            return
        with get_conn() as con:
            c = con.cursor()
            c.execute("SELECT pieza,sitio,ps,mg,ni,ss,sup,mov,nota FROM periodontics WHERE patient_id=?",
                      (self.patient_id,))
            for pieza, sitio, ps, mg, ni, ss, sup, mov, nota in c.fetchall():
                if pieza not in self.widgets: 
                    continue
                if sitio in self.sitios:
                    idx = self.sitios.index(sitio)
                    self.widgets[pieza]["ps"][idx].set(str(ps))
                    self.widgets[pieza]["ni"][idx].set(str(ni))
                    self.widgets[pieza]["ss"][idx].set(int(ss))
                    self.widgets[pieza]["sup"][idx].set(int(sup))
                # Campos generales
                self.widgets[pieza]["mg"].set(str(mg))
                self.widgets[pieza]["mov"].set(str(mov))
                self.widgets[pieza]["nota"].set(nota if nota else "")

    def save_all_to_db(self):
        """Guarda todos los datos de periodoncia en DB"""
        if not self.patient_id:
            messagebox.showwarning("Sin paciente", "Seleccione un paciente.")
            return
        with get_conn() as con:
            c = con.cursor()
            for pieza, vals in self.widgets.items():
                mg = self._to_float(vals["mg"].get())
                mov = self._to_int(vals["mov"].get())
                nota = vals["nota"].get()
                for i, sitio in enumerate(self.sitios):
                    ps = self._to_float(vals["ps"][i].get())
                    ni_raw = vals["ni"][i].get()
                    ni = ps - mg if ni_raw == "N/A" else self._to_float(ni_raw)
                    ss = int(vals["ss"][i].get())
                    sup = int(vals["sup"][i].get())
                    c.execute("""
                        INSERT OR REPLACE INTO periodontics
                        (patient_id,pieza,sitio,ps,mg,ni,ss,sup,mov,nota)
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                    """, (self.patient_id, pieza, sitio, ps, mg, ni, ss, sup, mov, nota))
            con.commit()
        messagebox.showinfo("OK", "Datos de periodoncia guardados.")

    def calculate_metrics(self):
        total_ps = total_ni = sas = sites = 0
        for pieza, vals in self.widgets.items():
            mg = self._to_float(vals["mg"].get())
            for i in range(6):
                ps = self._to_float(vals["ps"][i].get())
                ni = ps - mg if vals["ni"][i].get() == "N/A" else self._to_float(vals["ni"][i].get())
                total_ps += ps
                total_ni += ni
                sites += 1
                sas += int(vals["ss"][i].get())
        self.profundidad_media_var.set(f"{(total_ps / sites):.2f}" if sites else "0")
        self.nivel_insercion_var.set(f"{(total_ni / sites):.2f}" if sites else "0")
        self.porcentaje_sas_var.set(f"{(sas / sites * 100):.1f}%" if sites else "0")
        # El cálculo de placa no está implementado en tu código, por lo que no se actualiza
        self.porcentaje_placa_var.set("N/A")

    def clear_form(self, keep_zero=False):
        for vals in self.widgets.values():
            for v in vals["ps"]: v.set("0")
            for v in vals["ni"]: v.set("N/A")
            for v in vals["ss"]: v.set(0)
            for v in vals["sup"]: v.set(0)
            vals["mg"].set("0"); vals["mov"].set("0")
            vals["nota"].set("")
        self.profundidad_media_var.set(""); self.nivel_insercion_var.set(""); self.porcentaje_sas_var.set("")

    # ---------------- Import/Export ----------------
    def export_file(self):
        if not self.patient_id: return
        data = {"paciente": self.patient_id, "datos": []}
        for pieza, vals in self.widgets.items():
            d = {"pieza": pieza, "mg": vals["mg"].get(), "mov": vals["mov"].get(), "nota": vals["nota"].get(), "sitios": []}
            for i, sitio in enumerate(self.sitios):
                d["sitios"].append({
                    "sitio": sitio, "ps": vals["ps"][i].get(), "ni": vals["ni"][i].get(),
                    "ss": vals["ss"][i].get(), "sup": vals["sup"][i].get()
                })
            data["datos"].append(d)
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path: json.dump(data, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    def import_file(self):
        if not self.patient_id: return
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            data = json.load(open(path, "r", encoding="utf-8"))
            for d in data.get("datos", []):
                p = d["pieza"]
                if p not in self.widgets: continue
                self.widgets[p]["mg"].set(d.get("mg", "0"))
                self.widgets[p]["mov"].set(d.get("mov", "0"))
                self.widgets[p]["nota"].set(d.get("nota", ""))
                for s in d.get("sitios", []):
                    if s["sitio"] not in self.sitios: continue
                    idx = self.sitios.index(s["sitio"])
                    self.widgets[p]["ps"][idx].set(s.get("ps", "0"))
                    self.widgets[p]["ni"][idx].set(s.get("ni", "N/A"))
                    self.widgets[p]["ss"][idx].set(int(s.get("ss", 0)))
                    self.widgets[p]["sup"][idx].set(int(s.get("sup", 0)))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar: {e}")

    # ---------------- Helpers ----------------
    def _to_float(self, s):
        try: return float(s)
        except: return 0.0
    def _to_int(self, s):
        try: return int(float(s))
        except: return 0
# ----------------- Fin de la clase PeriodonticsTab -----------------

###############################################
# Ventana principal
###############################################
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DentalClinicApp")
        self.geometry("800x600")
        self.patient_id = None
        # Barra de estado del paciente
        self.patient_info_label = ttk.Label(self, text="No hay paciente seleccionado.")
        self.patient_info_label.pack(fill=tk.X, padx=10, pady=(6,0))
        # Notebook de pestañas
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        # Pestañas
        self.patients_tab = PatientsTab(self.notebook, self)
        self.history_tab = HistoryTab(self.notebook, self)
        self.treatments_tab = TreatmentsTab(self.notebook, self)
        self.appointments_tab = AppointmentsTab(self.notebook, self)
        self.odontogram_tab = OdontogramTab(self.notebook, self)
        self.periodontics_tab = PeriodonticsTab(self.notebook, self)
        # Añadir pestañas al notebook
        self.notebook.add(self.patients_tab, text="Pacientes")
        self.notebook.add(self.history_tab, text="Historia Clínica")
        self.notebook.add(self.treatments_tab, text="Tratamientos")
        self.notebook.add(self.appointments_tab, text="Agenda")
        self.notebook.add(self.odontogram_tab, text="Odontograma")
        self.notebook.add(self.periodontics_tab, text="Periodoncia")
        self.on_patient_change(None) # Llama al inicio para inicializar
    def on_patient_change(self, patient_id):
        self.patient_id = patient_id
        # Actualiza las pestañas con el paciente seleccionado
        self.history_tab.set_patient(patient_id)
        self.treatments_tab.set_patient(patient_id)
        self.odontogram_tab.set_patient(patient_id)
        self.periodontics_tab.set_patient(patient_id)
        # Actualiza la barra de información
        if patient_id:
            with get_conn() as con:
                c = con.cursor()
                c.execute("SELECT nombre, apellido, dni FROM patients WHERE id=?", (patient_id,))
                row = c.fetchone()
                if row:
                    nombre, apellido, dni = row
                    self.patient_info_label.config(text=f"Paciente actual: {apellido}, {nombre} (DNI: {dni}) - ID: {patient_id}")
                else:
                    self.patient_info_label.config(text="No hay paciente seleccionado.")
        else:
            self.patient_info_label.config(text="No hay paciente seleccionado.")
if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()
