#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Gestión Dental con Periodontograma
Aplicación completa para la gestión de pacientes y registros clínicos dentales
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime, date
import json
import re

class DentalManagementSystem:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Gestión Dental")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Inicializar base de datos
        self.init_database()

        # Variables
        self.current_patient_id = None
        self.selected_tooth = None
        self.selected_surface_obj = None

        # Colores para estados dentales
        self.tooth_colors = {
            'Sano': '#FFFFFF',
            'Caries': '#FF6347',
            'Restauración': '#4169E1',
            'Ausente': '#696969',
            'Implante': '#FFD700',
            'Corona': '#9370DB',
            'Endodoncia': '#FF69B4',
            'A-Extracción': '#FF0000',
        }
        
        self.tooth_objects = {}
        self.perio_entries = {}
        
        self.create_widgets()
        self.load_patients()

    def init_database(self):
        self.conn = sqlite3.connect('dental_clinic.db')
        self.cursor = self.conn.cursor()

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                dni TEXT UNIQUE NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                birth_date TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER UNIQUE,
                allergies TEXT,
                medications TEXT,
                diseases TEXT,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                reason TEXT,
                notes TEXT,
                status TEXT DEFAULT 'Programada',
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                observations TEXT,
                cost REAL,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS odontogram (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                tooth_number INTEGER,
                status TEXT,
                face TEXT,
                date_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS periodontogram (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                tooth_number INTEGER,
                ps_buccal REAL,
                mg_buccal REAL,
                ni_buccal REAL,
                ps_lingual REAL,
                mg_lingual REAL,
                ni_lingual REAL,
                bleeding_buccal BOOLEAN,
                suppuration_buccal BOOLEAN,
                bleeding_lingual BOOLEAN,
                suppuration_lingual BOOLEAN,
                mobility INTEGER,
                furcation TEXT,
                date_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')
        
        self.conn.commit()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.create_patients_tab()
        self.create_appointments_tab()
        self.create_odontogram_tab()
        self.create_periodontogram_tab()
        self.create_treatments_tab()
        
    def create_patients_tab(self):
        self.patients_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.patients_frame, text="Pacientes")
        search_frame = ttk.Frame(self.patients_frame)
        search_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(search_frame, text="Buscar:").pack(side='left', padx=(0,5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side='left', padx=(0,10))
        self.search_entry.bind('<KeyRelease>', self.search_patients)
        ttk.Button(search_frame, text="Nuevo Paciente", command=self.new_patient).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Editar", command=self.edit_patient).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Eliminar", command=self.delete_patient).pack(side='left', padx=5)
        columns = ('ID', 'Nombre', 'Apellido', 'DNI', 'Teléfono', 'Email')
        self.patients_tree = ttk.Treeview(self.patients_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.patients_tree.heading(col, text=col)
            self.patients_tree.column(col, width=120)
        scrollbar = ttk.Scrollbar(self.patients_frame, orient='vertical', command=self.patients_tree.yview)
        self.patients_tree.configure(yscrollcommand=scrollbar.set)
        self.patients_tree.pack(side='left', fill='both', expand=True, padx=(10,0), pady=10)
        scrollbar.pack(side='right', fill='y', padx=(0,10), pady=10)
        self.patients_tree.bind('<<TreeviewSelect>>', self.on_patient_select)

    def create_appointments_tab(self):
        self.appointments_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.appointments_frame, text="Citas")
        controls_frame = ttk.Frame(self.appointments_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(controls_frame, text="Nueva Cita", command=self.new_appointment).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Editar Cita", command=self.edit_appointment).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Cancelar Cita", command=self.cancel_appointment).pack(side='left', padx=5)
        apt_columns = ('ID', 'Fecha', 'Hora', 'Paciente', 'Motivo', 'Estado')
        self.appointments_tree = ttk.Treeview(self.appointments_frame, columns=apt_columns, show='headings', height=20)
        for col in apt_columns:
            self.appointments_tree.heading(col, text=col)
            self.appointments_tree.column(col, width=150)
        apt_scrollbar = ttk.Scrollbar(self.appointments_frame, orient='vertical', command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=apt_scrollbar.set)
        self.appointments_tree.pack(side='left', fill='both', expand=True, padx=(10,0), pady=10)
        apt_scrollbar.pack(side='right', fill='y', padx=(0,10), pady=10)
        self.load_appointments()

    def create_odontogram_tab(self):
        self.odontogram_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.odontogram_frame, text="Odontograma")
        patient_info_frame = ttk.LabelFrame(self.odontogram_frame, text="Paciente Seleccionado")
        patient_info_frame.pack(fill='x', padx=10, pady=5)
        self.patient_info_label = ttk.Label(patient_info_frame, text="Seleccione un paciente desde la pestaña Pacientes")
        self.patient_info_label.pack(pady=10)
        odonto_frame = ttk.LabelFrame(self.odontogram_frame, text="Odontograma")
        odonto_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self.odonto_canvas = tk.Canvas(odonto_frame, bg='white', height=400)
        self.odonto_canvas.pack(fill='both', expand=True, padx=10, pady=10)
        odonto_controls = ttk.Frame(odonto_frame)
        odonto_controls.pack(fill='x', padx=10, pady=5)
        self.tooth_info_label = ttk.Label(odonto_controls, text="Seleccione un diente/superficie", font=('Arial', 10, 'bold'))
        self.tooth_info_label.pack(pady=5)
        controls_subframe = ttk.Frame(odonto_controls)
        controls_subframe.pack(pady=5)
        ttk.Label(controls_subframe, text="Estado:").pack(side='left', padx=(0,5))
        self.tooth_status_var = tk.StringVar(value='Sano')
        status_combo = ttk.Combobox(controls_subframe, textvariable=self.tooth_status_var,
                                     values=list(self.tooth_colors.keys()), state='readonly', width=15)
        status_combo.pack(side='left', padx=(0,10))
        ttk.Button(controls_subframe, text="Aplicar Estado", command=self.apply_tooth_status).pack(side='left', padx=5)
        ttk.Button(controls_subframe, text="Aplicar a Todo el Diente", command=self.apply_to_whole_tooth).pack(side='left', padx=5)
        ttk.Button(controls_subframe, text="Guardar", command=self.save_odontogram).pack(side='left', padx=5)
        ttk.Button(controls_subframe, text="Limpiar Diente", command=self.clear_tooth).pack(side='left', padx=5)
        legend_frame = ttk.LabelFrame(odonto_frame, text="Leyenda")
        legend_frame.pack(fill='x', padx=10, pady=5)
        legend_canvas = tk.Canvas(legend_frame, height=50, bg='white')
        legend_canvas.pack(fill='x', padx=5, pady=5)
        x = 10
        for status, color in self.tooth_colors.items():
            legend_canvas.create_rectangle(x, 10, x+15, 25, fill=color, outline='black')
            legend_canvas.create_text(x+20, 17, text=status, anchor='w')
            x += 120
        self.draw_odontogram()

    def create_periodontogram_tab(self):
        self.periodonto_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.periodonto_frame, text="Periodontograma")

        perio_patient_frame = ttk.LabelFrame(self.periodonto_frame, text="Paciente Seleccionado")
        perio_patient_frame.pack(fill='x', padx=10, pady=5)
        self.perio_patient_label = ttk.Label(perio_patient_frame, text="Seleccione un paciente desde la pestaña Pacientes")
        self.perio_patient_label.pack(pady=10)

        perio_controls_frame = ttk.Frame(self.periodonto_frame)
        perio_controls_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(perio_controls_frame, text="Guardar Periodontograma", command=self.save_perio_measurements).pack(side='left', padx=5)
        
        # Contenedor principal con scrollbar
        self.perio_canvas = tk.Canvas(self.periodonto_frame, borderwidth=0, background="#ffffff")
        self.perio_frame = ttk.Frame(self.perio_canvas)
        self.perio_vbar = ttk.Scrollbar(self.periodonto_frame, orient="vertical", command=self.perio_canvas.yview)
        self.perio_canvas.configure(yscrollcommand=self.perio_vbar.set)

        self.perio_vbar.pack(side="right", fill="y")
        self.perio_canvas.pack(side="left", fill="both", expand=True)
        self.perio_canvas.create_window((4,4), window=self.perio_frame, anchor="nw",
                                      tags="self.perio_frame")
        self.perio_frame.bind("<Configure>", lambda event, canvas=self.perio_canvas: canvas.configure(scrollregion=canvas.bbox("all")))

        self.draw_periodontogram_grid()

    def draw_periodontogram_grid(self):
        """Dibuja la grilla del periodontograma en el frame."""
        for widget in self.perio_frame.winfo_children():
            widget.destroy()
        
        self.perio_entries = {}
        
        upper_teeth = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
        lower_teeth = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
        
        # --- Cabeceras de Maxilar Superior ---
        ttk.Label(self.perio_frame, text="MAXILAR SUPERIOR", font=('Arial', 10, 'bold')).grid(row=0, column=1, columnspan=len(upper_teeth), sticky='ew', pady=(5,0))
        
        # Fila de números de dientes superiores
        ttk.Label(self.perio_frame, text="").grid(row=1, column=0, sticky='nsew', padx=2, pady=2)
        for i, tooth_num in enumerate(upper_teeth):
            ttk.Label(self.perio_frame, text=str(tooth_num), font=('Arial', 10, 'bold')).grid(row=1, column=i+1, sticky='nsew', padx=2, pady=2)

        # Separador vertical central superior
        ttk.Separator(self.perio_frame, orient='vertical').grid(row=0, column=9, rowspan=21, sticky='ns', padx=1)
        
        # Filas de datos superiores
        upper_rows = [
            ('PS', 'Bucal', 'p'), ('MG', 'Bucal', 'p'), ('NI', 'Bucal', 'p'), ('Sangrado', 'Bucal', 'b'), ('Supuración', 'Bucal', 'b'),
            ('PS', 'Lingual', 'p'), ('MG', 'Lingual', 'p'), ('NI', 'Lingual', 'p'), ('Sangrado', 'Lingual', 'b'), ('Supuración', 'Lingual', 'b'),
        ]
        
        # Etiquetas de columnas de datos
        ttk.Label(self.perio_frame, text="Bucal", font=('Arial', 8, 'bold')).grid(row=2, column=0, sticky='w', padx=5)
        for i, (label, face, type) in enumerate(upper_rows[:5]):
            row_idx = i + 3
            ttk.Label(self.perio_frame, text=f"{label}", font=('Arial', 8)).grid(row=row_idx, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(self.perio_frame, text="Lingual", font=('Arial', 8, 'bold')).grid(row=8, column=0, sticky='w', padx=5)
        for i, (label, face, type) in enumerate(upper_rows[5:]):
            row_idx = i + 9
            ttk.Label(self.perio_frame, text=f"{label}", font=('Arial', 8)).grid(row=row_idx, column=0, sticky='w', padx=5, pady=2)
            
        for col_idx, tooth_num in enumerate(upper_teeth):
            for i, (label, face, type) in enumerate(upper_rows):
                if face == 'Bucal':
                    row_idx = i + 3
                else: # Lingual
                    row_idx = i + 9 - 5
                
                full_label = f"{tooth_num}_{face}_{label.replace(' ', '').lower()}"
                
                if type == 'b': # Boolean
                    var = tk.BooleanVar()
                    widget = ttk.Checkbutton(self.perio_frame, variable=var)
                    widget.grid(row=row_idx, column=col_idx+1, sticky='nsew', padx=2, pady=2)
                    self.perio_entries[full_label] = var
                else: # Entry
                    var = tk.StringVar()
                    widget = ttk.Entry(self.perio_frame, textvariable=var, width=5)
                    widget.grid(row=row_idx, column=col_idx+1, sticky='nsew', padx=2, pady=2)
                    self.perio_entries[full_label] = var
        
        # Filas de Movilidad y Furcación superior
        ttk.Label(self.perio_frame, text="Movilidad").grid(row=15, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(self.perio_frame, text="Furcación").grid(row=16, column=0, sticky='w', padx=5, pady=2)
        
        for col_idx, tooth_num in enumerate(upper_teeth):
            var_mov = tk.StringVar()
            widget_mov = ttk.Entry(self.perio_frame, textvariable=var_mov, width=5)
            widget_mov.grid(row=15, column=col_idx+1, sticky='nsew', padx=2, pady=2)
            self.perio_entries[f'{tooth_num}_movilidad'] = var_mov

            var_fur = tk.StringVar()
            widget_fur = ttk.Entry(self.perio_frame, textvariable=var_fur, width=5)
            widget_fur.grid(row=16, column=col_idx+1, sticky='nsew', padx=2, pady=2)
            self.perio_entries[f'{tooth_num}_furcacion'] = var_fur
        
        # Separador horizontal entre maxilares
        ttk.Separator(self.perio_frame, orient='horizontal').grid(row=17, column=0, columnspan=len(upper_teeth)+1, sticky='ew', pady=10)
        
        # --- Cabeceras de Maxilar Inferior ---
        ttk.Label(self.perio_frame, text="MAXILAR INFERIOR", font=('Arial', 10, 'bold')).grid(row=18, column=1, columnspan=len(lower_teeth), sticky='ew', pady=(5,0))
        
        # Fila de números de dientes inferiores
        ttk.Label(self.perio_frame, text="").grid(row=19, column=0, sticky='nsew', padx=2, pady=2)
        for i, tooth_num in enumerate(lower_teeth):
            ttk.Label(self.perio_frame, text=str(tooth_num), font=('Arial', 10, 'bold')).grid(row=19, column=i+1, sticky='nsew', padx=2, pady=2)

        # Separador vertical central inferior
        ttk.Separator(self.perio_frame, orient='vertical').grid(row=18, column=9, rowspan=21, sticky='ns', padx=1)
        
        # Filas de datos inferiores (iguales a las superiores)
        lower_rows = [
            ('PS', 'Bucal', 'p'), ('MG', 'Bucal', 'p'), ('NI', 'Bucal', 'p'), ('Sangrado', 'Bucal', 'b'), ('Supuración', 'Bucal', 'b'),
            ('PS', 'Lingual', 'p'), ('MG', 'Lingual', 'p'), ('NI', 'Lingual', 'p'), ('Sangrado', 'Lingual', 'b'), ('Supuración', 'Lingual', 'b'),
        ]

        # Etiquetas de columnas de datos inferiores
        ttk.Label(self.perio_frame, text="Bucal", font=('Arial', 8, 'bold')).grid(row=20, column=0, sticky='w', padx=5)
        for i, (label, face, type) in enumerate(lower_rows[:5]):
            row_idx = i + 21
            ttk.Label(self.perio_frame, text=f"{label}", font=('Arial', 8)).grid(row=row_idx, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(self.perio_frame, text="Lingual", font=('Arial', 8, 'bold')).grid(row=26, column=0, sticky='w', padx=5)
        for i, (label, face, type) in enumerate(lower_rows[5:]):
            row_idx = i + 27
            ttk.Label(self.perio_frame, text=f"{label}", font=('Arial', 8)).grid(row=row_idx, column=0, sticky='w', padx=5, pady=2)
            
        for col_idx, tooth_num in enumerate(lower_teeth):
            for i, (label, face, type) in enumerate(lower_rows):
                if face == 'Bucal':
                    row_idx = i + 21
                else: # Lingual
                    row_idx = i + 27 - 5
                
                full_label = f"{tooth_num}_{face}_{label.replace(' ', '').lower()}"
                
                if type == 'b': # Boolean
                    var = tk.BooleanVar()
                    widget = ttk.Checkbutton(self.perio_frame, variable=var)
                    widget.grid(row=row_idx, column=col_idx+1, sticky='nsew', padx=2, pady=2)
                    self.perio_entries[full_label] = var
                else: # Entry
                    var = tk.StringVar()
                    widget = ttk.Entry(self.perio_frame, textvariable=var, width=5)
                    widget.grid(row=row_idx, column=col_idx+1, sticky='nsew', padx=2, pady=2)
                    self.perio_entries[full_label] = var

        # Filas de Movilidad y Furcación inferior
        ttk.Label(self.perio_frame, text="Movilidad").grid(row=32, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(self.perio_frame, text="Furcación").grid(row=33, column=0, sticky='w', padx=5, pady=2)
        
        for col_idx, tooth_num in enumerate(lower_teeth):
            var_mov = tk.StringVar()
            widget_mov = ttk.Entry(self.perio_frame, textvariable=var_mov, width=5)
            widget_mov.grid(row=32, column=col_idx+1, sticky='nsew', padx=2, pady=2)
            self.perio_entries[f'{tooth_num}_movilidad'] = var_mov

            var_fur = tk.StringVar()
            widget_fur = ttk.Entry(self.perio_frame, textvariable=var_fur, width=5)
            widget_fur.grid(row=33, column=col_idx+1, sticky='nsew', padx=2, pady=2)
            self.perio_entries[f'{tooth_num}_furcacion'] = var_fur

        # Hacer que las columnas se expandan
        # Se elimina esta parte para evitar que las columnas se estiren automáticamente.
        # for i in range(len(upper_teeth) + 1):
        #     self.perio_frame.grid_columnconfigure(i, weight=1)

    def load_perio_measurements(self):
        """Carga las mediciones del periodontograma desde la base de datos a la grilla."""
        if not self.current_patient_id:
            return

        self.cursor.execute('''
            SELECT * FROM periodontogram WHERE patient_id = ?
        ''', (self.current_patient_id,))
        results = self.cursor.fetchall()
        
        perio_data = {row[2]: row[3:] for row in results}
        
        all_teeth = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28,
                         48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
        
        for tooth_num in all_teeth:
            if tooth_num in perio_data:
                data = perio_data[tooth_num]
                
                # Cargar datos bucales
                if f'{tooth_num}_Bucal_ps' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Bucal_ps'].set(f"{data[0]:.1f}" if data[0] is not None else "")
                if f'{tooth_num}_Bucal_mg' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Bucal_mg'].set(f"{data[1]:.1f}" if data[1] is not None else "")
                if f'{tooth_num}_Bucal_ni' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Bucal_ni'].set(f"{data[2]:.1f}" if data[2] is not None else "")
                if f'{tooth_num}_Bucal_sangrado' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Bucal_sangrado'].set(data[6])
                if f'{tooth_num}_Bucal_supuracion' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Bucal_supuracion'].set(data[7])

                # Cargar datos linguales
                if f'{tooth_num}_Lingual_ps' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Lingual_ps'].set(f"{data[3]:.1f}" if data[3] is not None else "")
                if f'{tooth_num}_Lingual_mg' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Lingual_mg'].set(f"{data[4]:.1f}" if data[4] is not None else "")
                if f'{tooth_num}_Lingual_ni' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Lingual_ni'].set(f"{data[5]:.1f}" if data[5] is not None else "")
                if f'{tooth_num}_Lingual_sangrado' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Lingual_sangrado'].set(data[8])
                if f'{tooth_num}_Lingual_supuracion' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_Lingual_supuracion'].set(data[9])
                
                # Cargar movilidad y furcación
                if f'{tooth_num}_movilidad' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_movilidad'].set(data[10] or "")
                if f'{tooth_num}_furcacion' in self.perio_entries:
                    self.perio_entries[f'{tooth_num}_furcacion'].set(data[11] or "")

    def save_perio_measurements(self):
        """Guarda todas las mediciones de la grilla en la base de datos."""
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente primero.")
            return

        all_teeth = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28,
                         48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]

        # Validar los datos antes de eliminarlos
        for tooth_num in all_teeth:
            try:
                ps_b = self.perio_entries[f'{tooth_num}_Bucal_ps'].get() if f'{tooth_num}_Bucal_ps' in self.perio_entries else None
                mg_b = self.perio_entries[f'{tooth_num}_Bucal_mg'].get() if f'{tooth_num}_Bucal_mg' in self.perio_entries else None
                ni_b = self.perio_entries[f'{tooth_num}_Bucal_ni'].get() if f'{tooth_num}_Bucal_ni' in self.perio_entries else None
                ps_l = self.perio_entries[f'{tooth_num}_Lingual_ps'].get() if f'{tooth_num}_Lingual_ps' in self.perio_entries else None
                mg_l = self.perio_entries[f'{tooth_num}_Lingual_mg'].get() if f'{tooth_num}_Lingual_mg' in self.perio_entries else None
                ni_l = self.perio_entries[f'{tooth_num}_Lingual_ni'].get() if f'{tooth_num}_Lingual_ni' in self.perio_entries else None
                mobility = self.perio_entries[f'{tooth_num}_movilidad'].get() if f'{tooth_num}_movilidad' in self.perio_entries else None

                if ps_b and not ps_b.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para PS Bucal del diente {tooth_num}")
                if mg_b and not mg_b.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para MG Bucal del diente {tooth_num}")
                if ni_b and not ni_b.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para NI Bucal del diente {tooth_num}")
                if ps_l and not ps_l.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para PS Lingual del diente {tooth_num}")
                if mg_l and not mg_l.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para MG Lingual del diente {tooth_num}")
                if ni_l and not ni_l.replace('.', '', 1).isdigit(): raise ValueError(f"Valor no numérico para NI Lingual del diente {tooth_num}")
                if mobility and not mobility.isdigit(): raise ValueError(f"Valor no numérico para Movilidad del diente {tooth_num}")
                
            except ValueError as e:
                messagebox.showwarning("Advertencia", str(e))
                return

        self.cursor.execute('DELETE FROM periodontogram WHERE patient_id = ?', (self.current_patient_id,))
        
        for tooth_num in all_teeth:
            ps_b = self.perio_entries[f'{tooth_num}_Bucal_ps'].get() if f'{tooth_num}_Bucal_ps' in self.perio_entries else None
            mg_b = self.perio_entries[f'{tooth_num}_Bucal_mg'].get() if f'{tooth_num}_Bucal_mg' in self.perio_entries else None
            ni_b = self.perio_entries[f'{tooth_num}_Bucal_ni'].get() if f'{tooth_num}_Bucal_ni' in self.perio_entries else None
            bleed_b = self.perio_entries[f'{tooth_num}_Bucal_sangrado'].get() if f'{tooth_num}_Bucal_sangrado' in self.perio_entries else None
            supp_b = self.perio_entries[f'{tooth_num}_Bucal_supuracion'].get() if f'{tooth_num}_Bucal_supuracion' in self.perio_entries else None
            
            ps_l = self.perio_entries[f'{tooth_num}_Lingual_ps'].get() if f'{tooth_num}_Lingual_ps' in self.perio_entries else None
            mg_l = self.perio_entries[f'{tooth_num}_Lingual_mg'].get() if f'{tooth_num}_Lingual_mg' in self.perio_entries else None
            ni_l = self.perio_entries[f'{tooth_num}_Lingual_ni'].get() if f'{tooth_num}_Lingual_ni' in self.perio_entries else None
            bleed_l = self.perio_entries[f'{tooth_num}_Lingual_sangrado'].get() if f'{tooth_num}_Lingual_sangrado' in self.perio_entries else None
            supp_l = self.perio_entries[f'{tooth_num}_Lingual_supuracion'].get() if f'{tooth_num}_Lingual_supuracion' in self.perio_entries else None

            mobility = self.perio_entries[f'{tooth_num}_movilidad'].get() if f'{tooth_num}_movilidad' in self.perio_entries else None
            furcation = self.perio_entries[f'{tooth_num}_furcacion'].get() if f'{tooth_num}_furcacion' in self.perio_entries else None
            
            ps_b = float(ps_b) if ps_b else None
            mg_b = float(mg_b) if mg_b else None
            ni_b = float(ni_b) if ni_b else None
            ps_l = float(ps_l) if ps_l else None
            mg_l = float(mg_l) if mg_l else None
            ni_l = float(ni_l) if ni_l else None
            mobility = int(mobility) if mobility else None

            self.cursor.execute('''
                INSERT INTO periodontogram (
                    patient_id, tooth_number, ps_buccal, mg_buccal, ni_buccal,
                    ps_lingual, mg_lingual, ni_lingual, bleeding_buccal,
                    suppuration_buccal, bleeding_lingual, suppuration_lingual,
                    mobility, furcation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.current_patient_id, tooth_num, ps_b, mg_b, ni_b,
                ps_l, mg_l, ni_l, bleed_b, supp_b, bleed_l, supp_l,
                mobility, furcation
            ))

        self.conn.commit()
        messagebox.showinfo("Éxito", "Periodontograma guardado correctamente.")

    def create_treatments_tab(self):
        self.treatments_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.treatments_frame, text="Tratamientos")
        treat_patient_frame = ttk.LabelFrame(self.treatments_frame, text="Paciente Seleccionado")
        treat_patient_frame.pack(fill='x', padx=10, pady=5)
        self.treat_patient_label = ttk.Label(treat_patient_frame, text="Seleccione un paciente desde la pestaña Pacientes")
        self.treat_patient_label.pack(pady=10)
        treat_controls = ttk.Frame(self.treatments_frame)
        treat_controls.pack(fill='x', padx=10, pady=5)
        ttk.Button(treat_controls, text="Nuevo Tratamiento", command=self.new_treatment).pack(side='left', padx=5)
        ttk.Button(treat_controls, text="Editar Historia Médica", command=self.edit_medical_history).pack(side='left', padx=5)
        medical_frame = ttk.LabelFrame(self.treatments_frame, text="Historia Médica")
        medical_frame.pack(fill='x', padx=10, pady=5)
        self.medical_text = tk.Text(medical_frame, height=4, wrap=tk.WORD, state='disabled')
        medical_scroll = ttk.Scrollbar(medical_frame, orient='vertical', command=self.medical_text.yview)
        self.medical_text.configure(yscrollcommand=medical_scroll.set)
        self.medical_text.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        medical_scroll.pack(side='right', fill='y', pady=5)
        treat_frame = ttk.LabelFrame(self.treatments_frame, text="Historial de Tratamientos")
        treat_frame.pack(fill='both', expand=True, padx=10, pady=5)
        treat_columns = ('ID', 'Fecha', 'Descripción', 'Observaciones', 'Costo')
        self.treatments_tree = ttk.Treeview(treat_frame, columns=treat_columns, show='headings', height=12)
        for col in treat_columns:
            self.treatments_tree.heading(col, text=col)
            if col == 'Descripción':
                self.treatments_tree.column(col, width=300)
            else:
                self.treatments_tree.column(col, width=120)
        treat_scrollbar = ttk.Scrollbar(treat_frame, orient='vertical', command=self.treatments_tree.yview)
        self.treatments_tree.configure(yscrollcommand=treat_scrollbar.set)
        self.treatments_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        treat_scrollbar.pack(side='right', fill='y', pady=5)
        
    def draw_odontogram(self):
        """Dibuja el odontograma profesional en el canvas"""
        self.odonto_canvas.delete("all")
        self.tooth_objects = {}

        tooth_size = 35
        spacing = 8
        start_x_left = 50
        start_x_right = 500
        upper_y = 60
        lower_y = 250
        
        quadrants_config = {
            1: {'numbers': list(range(18, 10, -1)), 'start_x': start_x_left, 'y': upper_y, 'label': 'Cuadrante 1 (Superior Derecho)'},
            2: {'numbers': list(range(21, 29)), 'start_x': start_x_right, 'y': upper_y, 'label': 'Cuadrante 2 (Superior Izquierdo)'},
            3: {'numbers': list(range(31, 39)), 'start_x': start_x_right, 'y': lower_y, 'label': 'Cuadrante 3 (Inferior Izquierdo)'},
            4: {'numbers': list(range(48, 40, -1)), 'start_x': start_x_left, 'y': lower_y, 'label': 'Cuadrante 4 (Inferior Derecho)'}
        }

        self.odonto_canvas.create_text(250, 30, text="MAXILAR SUPERIOR", font=('Arial', 12, 'bold'), fill='navy')
        self.odonto_canvas.create_text(250, 320, text="MAXILAR INFERIOR", font=('Arial', 12, 'bold'), fill='navy')
        canvas_width = 900
        center_x = canvas_width // 2
        self.odonto_canvas.create_line(center_x, 50, center_x, 300, fill='gray', width=2, dash=(5, 5))

        for quad_num, config in quadrants_config.items():
            self.draw_quadrant(quad_num, config)

        self.odonto_canvas.create_line(40, upper_y + tooth_size + 20, canvas_width - 40, upper_y + tooth_size + 20, fill='lightgray', width=1)
        self.odonto_canvas.create_line(40, lower_y - 20, canvas_width - 40, lower_y - 20, fill='lightgray', width=1)
    
    def draw_quadrant(self, quad_num, config):
        """Dibuja un cuadrante específico del odontograma"""
        tooth_size = 35
        spacing = 8
        
        for i, tooth_num in enumerate(config['numbers']):
            x = config['start_x'] + i * (tooth_size + spacing)
            y = config['y']
            tooth_group = self.create_tooth_surfaces(x, y, tooth_size, tooth_num)
            self.tooth_objects[tooth_num] = tooth_group

    def create_tooth_surfaces(self, x, y, size, tooth_num):
        """Crea las 5 superficies de un diente (oclusal + 4 caras)"""
        tooth_surfaces = {}
        center_size = size * 0.4
        center_x = x + (size - center_size) // 2
        center_y = y + (size - center_size) // 2
        
        oclusal = self.odonto_canvas.create_rectangle(center_x, center_y, center_x + center_size, center_y + center_size, fill='white', outline='black', width=1, tags=f"tooth_{tooth_num}")
        tooth_surfaces['O'] = oclusal
        mesial = self.odonto_canvas.create_rectangle(x, center_y, center_x, center_y + center_size, fill='white', outline='black', width=1, tags=f"tooth_{tooth_num}")
        tooth_surfaces['M'] = mesial
        distal = self.odonto_canvas.create_rectangle(center_x + center_size, center_y, x + size, center_y + center_size, fill='white', outline='black', width=1, tags=f"tooth_{tooth_num}")
        tooth_surfaces['D'] = distal
        vestibular = self.odonto_canvas.create_rectangle(center_x, y, center_x + center_size, center_y, fill='white', outline='black', width=1, tags=f"tooth_{tooth_num}")
        tooth_surfaces['V'] = vestibular
        palatina = self.odonto_canvas.create_rectangle(center_x, center_y + center_size, center_x + center_size, y + size, fill='white', outline='black', width=1, tags=f"tooth_{tooth_num}")
        tooth_surfaces['P'] = palatina
        frame = self.odonto_canvas.create_rectangle(x, y, x + size, y + size, fill='', outline='black', width=2, tags=f"tooth_{tooth_num}")
        tooth_surfaces['frame'] = frame
        number_text = self.odonto_canvas.create_text(x + size//2, y + size + 15, text=str(tooth_num), font=('Arial', 9, 'bold'), tags=f"tooth_{tooth_num}")
        tooth_surfaces['number'] = number_text

        for surface, obj in tooth_surfaces.items():
            if surface not in ['frame', 'number']:
                self.odonto_canvas.tag_bind(obj, '<Button-1>', lambda e, tn=tooth_num, s=surface: self.select_tooth_surface(tn, s))
                self.odonto_canvas.tag_bind(obj, '<Button-3>', lambda e, tn=tooth_num, s=surface: self.show_surface_menu(e, tn, s))

        return tooth_surfaces

    def select_tooth_surface(self, tooth_number, surface):
        if self.selected_surface_obj:
            self.odonto_canvas.itemconfig(self.selected_surface_obj, outline='black', width=1)
        if self.selected_tooth and self.selected_tooth[0] in self.tooth_objects:
            self.odonto_canvas.itemconfig(self.tooth_objects[self.selected_tooth[0]]['frame'], outline='black', width=2)
        self.selected_tooth = (tooth_number, surface)
        self.selected_surface_obj = self.tooth_objects[tooth_number][surface]
        self.odonto_canvas.itemconfig(self.selected_surface_obj, outline='red', width=2)
        self.odonto_canvas.itemconfig(self.tooth_objects[tooth_number]['frame'], outline='red', width=3)
        self.update_tooth_info(tooth_number, surface)

    def show_surface_menu(self, event, tooth_number, surface):
        menu = tk.Menu(self.root, tearoff=0)
        for status in self.tooth_colors.keys():
            menu.add_command(
                label=status,
                command=lambda s=status: self.apply_surface_status(tooth_number, surface, s)
            )
        menu.add_separator()
        menu.add_command(
            label="Limpiar",
            command=lambda: self.apply_surface_status(tooth_number, surface, 'Sano')
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def apply_surface_status(self, tooth_number, surface, status):
        if tooth_number in self.tooth_objects and surface in self.tooth_objects[tooth_number]:
            color = self.tooth_colors.get(status, '#FFFFFF')
            self.odonto_canvas.itemconfig(self.tooth_objects[tooth_number][surface], fill=color)

    def update_tooth_info(self, tooth_number, surface):
        surface_names = {
            'O': 'Oclusal/Incisal',
            'M': 'Mesial',
            'D': 'Distal',
            'V': 'Vestibular',
            'P': 'Palatina/Lingual'
        }
        info_text = f"Diente: {tooth_number} - Superficie: {surface_names.get(surface, surface)}"
        if hasattr(self, 'tooth_info_label'):
            self.tooth_info_label.config(text=info_text)

    def select_tooth(self, tooth_number):
        self.select_tooth_surface(tooth_number, 'O')

    def apply_tooth_status(self):
        if not hasattr(self, 'selected_tooth') or not self.selected_tooth:
            messagebox.showwarning("Advertencia", "Seleccione un diente/superficie primero")
            return
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente primero")
            return
        tooth_number, surface = self.selected_tooth
        status = self.tooth_status_var.get()
        self.apply_surface_status(tooth_number, surface, status)

    def save_odontogram(self):
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente primero")
            return
        self.cursor.execute('DELETE FROM odontogram WHERE patient_id = ?', (self.current_patient_id,))
        for tooth_num, surfaces in self.tooth_objects.items():
            for surface_code, surface_obj in surfaces.items():
                if surface_code not in ['frame', 'number']:
                    color = self.odonto_canvas.itemcget(surface_obj, 'fill')
                    status = 'Sano'
                    for state, state_color in self.tooth_colors.items():
                        if color.lower() == state_color.lower():
                            status = state
                            break
                    if status != 'Sano':
                        self.cursor.execute('''
                            INSERT INTO odontogram (patient_id, tooth_number, status, face, date_updated)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (self.current_patient_id, tooth_num, status, surface_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.conn.commit()
        messagebox.showinfo("Éxito", "Odontograma guardado correctamente")

    def load_odontogram(self):
        if not self.current_patient_id:
            return
        for tooth_num, surfaces in self.tooth_objects.items():
            for surface_code, surface_obj in surfaces.items():
                if surface_code not in ['frame', 'number']:
                    self.odonto_canvas.itemconfig(surface_obj, fill='white')
        self.cursor.execute('''
            SELECT tooth_number, status, face FROM odontogram WHERE patient_id = ?
        ''', (self.current_patient_id,))
        results = self.cursor.fetchall()
        for tooth_num, status, face in results:
            if tooth_num in self.tooth_objects and face in self.tooth_objects[tooth_num]:
                color = self.tooth_colors.get(status, '#FFFFFF')
                self.odonto_canvas.itemconfig(
                    self.tooth_objects[tooth_num][face], fill=color
                )

    def apply_to_whole_tooth(self):
        if not hasattr(self, 'selected_tooth') or not self.selected_tooth:
            messagebox.showwarning("Advertencia", "Seleccione un diente primero")
            return
        tooth_number, _ = self.selected_tooth
        status = self.tooth_status_var.get()
        surfaces = ['O', 'M', 'D', 'V', 'P']
        for surface in surfaces:
            self.apply_surface_status(tooth_number, surface, status)

    def clear_tooth(self):
        if not hasattr(self, 'selected_tooth') or not self.selected_tooth:
            messagebox.showwarning("Advertencia", "Seleccione un diente primero")
            return
        tooth_number, _ = self.selected_tooth
        surfaces = ['O', 'M', 'D', 'V', 'P']
        for surface in surfaces:
            self.apply_surface_status(tooth_number, surface, 'Sano')

    def load_patients(self):
        for item in self.patients_tree.get_children():
            self.patients_tree.delete(item)
        self.cursor.execute('''
            SELECT id, name, surname, dni, phone, email FROM patients ORDER BY surname, name
        ''')
        for row in self.cursor.fetchall():
            self.patients_tree.insert('', 'end', values=row)

    def search_patients(self, event=None):
        search_term = self.search_var.get().lower()
        for item in self.patients_tree.get_children():
            self.patients_tree.delete(item)
        if search_term:
            self.cursor.execute('''
                SELECT id, name, surname, dni, phone, email FROM patients
                WHERE LOWER(name) LIKE ? OR LOWER(surname) LIKE ? OR dni LIKE ?
                ORDER BY surname, name
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            self.cursor.execute('''
                SELECT id, name, surname, dni, phone, email FROM patients ORDER BY surname, name
            ''')
        for row in self.cursor.fetchall():
            self.patients_tree.insert('', 'end', values=row)

    def new_patient(self):
        PatientDialog(self, "Nuevo Paciente")

    def edit_patient(self):
        selection = self.patients_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione un paciente para editar")
            return
        patient_id = self.patients_tree.item(selection[0])['values'][0]
        PatientDialog(self, "Editar Paciente", patient_id)

    def delete_patient(self):
        selection = self.patients_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione un paciente para eliminar")
            return
        if messagebox.askyesno("Confirmar", "¿Está seguro de eliminar este paciente?"):
            patient_id = self.patients_tree.item(selection[0])['values'][0]
            tables = ['medical_history', 'appointments', 'treatments', 'odontogram', 'periodontogram', 'patients']
            for table in tables:
                self.cursor.execute(f'DELETE FROM {table} WHERE patient_id = ?', (patient_id,))
            self.conn.commit()
            self.load_patients()
            messagebox.showinfo("Éxito", "Paciente eliminado correctamente")

    def on_patient_select(self, event):
        selection = self.patients_tree.selection()
        if selection:
            patient_data = self.patients_tree.item(selection[0])['values']
            self.current_patient_id = patient_data[0]
            patient_name = f"{patient_data[1]} {patient_data[2]} (DNI: {patient_data[3]})"
            self.patient_info_label.config(text=patient_name)
            self.perio_patient_label.config(text=patient_name)
            self.treat_patient_label.config(text=patient_name)
            self.load_odontogram()
            self.load_perio_measurements()
            self.load_medical_history()
            self.load_treatments()

    def load_appointments(self):
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)
        self.cursor.execute('''
            SELECT a.id, a.date, a.time, p.name || ' ' || p.surname AS patient_name, a.reason, a.status FROM appointments a INNER JOIN patients p ON a.patient_id = p.id ORDER BY a.date, a.time
        ''')
        for row in self.cursor.fetchall():
            self.appointments_tree.insert('', 'end', values=row)

    def new_appointment(self):
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente para la cita.")
            return
        AppointmentDialog(self, "Nueva Cita")

    def edit_appointment(self):
        selection = self.appointments_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una cita para editar")
            return
        appointment_id = self.appointments_tree.item(selection[0])['values'][0]
        AppointmentDialog(self, "Editar Cita", appointment_id)

    def cancel_appointment(self):
        selection = self.appointments_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una cita para cancelar")
            return
        appointment_id = self.appointments_tree.item(selection[0])['values'][0]
        if messagebox.askyesno("Confirmar", "¿Está seguro de cancelar esta cita?"):
            self.cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', ('Cancelada', appointment_id))
            self.conn.commit()
            self.load_appointments()
            messagebox.showinfo("Éxito", "Cita cancelada correctamente")

    def load_treatments(self):
        for item in self.treatments_tree.get_children():
            self.treatments_tree.delete(item)
        if self.current_patient_id:
            self.cursor.execute('''
                SELECT id, date, description, observations, cost FROM treatments WHERE patient_id = ? ORDER BY date DESC
            ''', (self.current_patient_id,))
            for row in self.cursor.fetchall():
                self.treatments_tree.insert('', 'end', values=row)

    def new_treatment(self):
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente para registrar un tratamiento.")
            return
        TreatmentDialog(self, "Nuevo Tratamiento")

    def load_medical_history(self):
        self.medical_text.config(state='normal')
        self.medical_text.delete(1.0, tk.END)
        if self.current_patient_id:
            self.cursor.execute('''
                SELECT allergies, medications, diseases, notes FROM medical_history WHERE patient_id = ?
            ''', (self.current_patient_id,))
            result = self.cursor.fetchone()
            if result:
                history = f"Alergias: {result[0] or 'N/A'}\nMedicamentos: {result[1] or 'N/A'}\nEnfermedades: {result[2] or 'N/A'}\nNotas: {result[3] or 'N/A'}"
                self.medical_text.insert(1.0, history)
        self.medical_text.config(state='disabled')
        
    def edit_medical_history(self):
        if not self.current_patient_id:
            messagebox.showwarning("Advertencia", "Seleccione un paciente para editar su historia médica.")
            return
        MedicalHistoryDialog(self, "Editar Historia Médica")

    def get_all_teeth_numbers(self):
        return [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 48, 47, 46, 45, 44, 43, 42, 41]

# Clases de diálogo para las ventanas
class PatientDialog(tk.Toplevel):
    def __init__(self, parent, title, patient_id=None):
        super().__init__(parent.root)
        self.parent = parent
        self.title(title)
        self.patient_id = patient_id
        self.transient(parent.root)
        self.grab_set()

        self.entries = {}
        fields = ['name', 'surname', 'dni', 'phone', 'email', 'address', 'birth_date']
        labels = ['Nombre', 'Apellido', 'DNI', 'Teléfono', 'Email', 'Dirección', 'Fecha de Nacimiento (YYYY-MM-DD)']

        for label, field in zip(labels, fields):
            row = ttk.Frame(self)
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            ttk.Label(row, text=label, width=25).pack(side=tk.LEFT)
            entry = ttk.Entry(row)
            entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
            self.entries[field] = entry
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="Guardar", command=self.save).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancelar", command=self.destroy).pack(side='left', padx=5)

        if self.patient_id:
            self.load_data()
            
    def load_data(self):
        self.parent.cursor.execute('SELECT * FROM patients WHERE id = ?', (self.patient_id,))
        data = self.parent.cursor.fetchone()
        if data:
            fields = ['id', 'name', 'surname', 'dni', 'phone', 'email', 'address', 'birth_date']
            for field, value in zip(fields, data):
                if field in self.entries:
                    self.entries[field].insert(0, value)

    def save(self):
        data = {field: entry.get().strip() for field, entry in self.entries.items()}

        # Validaciones
        if not data['name'] or not data['surname'] or not data['dni']:
            messagebox.showwarning("Advertencia", "Nombre, apellido y DNI son obligatorios.")
            return
        
        if not data['dni'].isdigit():
            messagebox.showwarning("Advertencia", "El DNI debe contener solo números.")
            return

        if data['phone'] and not data['phone'].isdigit():
            messagebox.showwarning("Advertencia", "El teléfono debe contener solo números.")
            return

        if data['email'] and not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
            messagebox.showwarning("Advertencia", "El formato del email es inválido.")
            return

        if self.patient_id:
            self.parent.cursor.execute('''
                UPDATE patients SET name = ?, surname = ?, dni = ?, phone = ?, email = ?, address = ?, birth_date = ?
                WHERE id = ?
            ''', (data['name'], data['surname'], data['dni'], data['phone'], data['email'], data['address'], data['birth_date'], self.patient_id))
        else:
            try:
                self.parent.cursor.execute('''
                    INSERT INTO patients (name, surname, dni, phone, email, address, birth_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (data['name'], data['surname'], data['dni'], data['phone'], data['email'], data['address'], data['birth_date']))
            except sqlite3.IntegrityError:
                messagebox.showwarning("Error", "Ya existe un paciente con este DNI.")
                return

        self.parent.conn.commit()
        self.parent.load_patients()
        self.destroy()

class AppointmentDialog(tk.Toplevel):
    def __init__(self, parent, title, appointment_id=None):
        super().__init__(parent.root)
        self.parent = parent
        self.title(title)
        self.appointment_id = appointment_id
        self.transient(parent.root)
        self.grab_set()

        self.entries = {}
        fields = ['date', 'time', 'reason', 'notes', 'status']
        labels = ['Fecha (YYYY-MM-DD)', 'Hora (HH:MM)', 'Motivo', 'Notas', 'Estado']

        for label, field in zip(labels, fields):
            row = ttk.Frame(self)
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            ttk.Label(row, text=label, width=25).pack(side=tk.LEFT)
            entry = ttk.Entry(row)
            entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
            self.entries[field] = entry
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="Guardar", command=self.save).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancelar", command=self.destroy).pack(side='left', padx=5)

        if self.appointment_id:
            self.load_data()

    def load_data(self):
        self.parent.cursor.execute('SELECT date, time, reason, notes, status FROM appointments WHERE id = ?', (self.appointment_id,))
        data = self.parent.cursor.fetchone()
        if data:
            fields = ['date', 'time', 'reason', 'notes', 'status']
            for field, value in zip(fields, data):
                if field in self.entries:
                    self.entries[field].insert(0, value)

    def save(self):
        data = {field: entry.get().strip() for field, entry in self.entries.items()}

        # Validaciones de fecha y hora
        if not all([data['date'], data['time']]):
            messagebox.showwarning("Advertencia", "Fecha y hora son obligatorios.")
            return

        try:
            datetime.strptime(data['date'], '%Y-%m-%d')
            datetime.strptime(data['time'], '%H:%M')
        except ValueError:
            messagebox.showwarning("Advertencia", "El formato de fecha (YYYY-MM-DD) o hora (HH:MM) es inválido.")
            return

        if self.appointment_id:
            self.parent.cursor.execute('''
                UPDATE appointments SET date = ?, time = ?, reason = ?, notes = ?, status = ?
                WHERE id = ?
            ''', (data['date'], data['time'], data['reason'], data['notes'], data['status'], self.appointment_id))
        else:
            self.parent.cursor.execute('''
                INSERT INTO appointments (patient_id, date, time, reason, notes, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.parent.current_patient_id, data['date'], data['time'], data['reason'], data['notes'], data['status']))
        
        self.parent.conn.commit()
        self.parent.load_appointments()
        self.destroy()

class TreatmentDialog(tk.Toplevel):
    def __init__(self, parent, title, treatment_id=None):
        super().__init__(parent.root)
        self.parent = parent
        self.title(title)
        self.treatment_id = treatment_id
        self.transient(parent.root)
        self.grab_set()

        self.entries = {}
        fields = ['date', 'description', 'observations', 'cost']
        labels = ['Fecha (YYYY-MM-DD)', 'Descripción', 'Observaciones', 'Costo']

        for label, field in zip(labels, fields):
            row = ttk.Frame(self)
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            ttk.Label(row, text=label, width=25).pack(side=tk.LEFT)
            if field == 'description' or field == 'observations':
                text_widget = tk.Text(row, height=4, width=30)
                text_widget.pack(side=tk.RIGHT, expand=True, fill=tk.X)
                self.entries[field] = text_widget
            else:
                entry = ttk.Entry(row)
                entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
                self.entries[field] = entry
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="Guardar", command=self.save).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancelar", command=self.destroy).pack(side='left', padx=5)

        if self.treatment_id:
            self.load_data()

    def load_data(self):
        self.parent.cursor.execute('SELECT date, description, observations, cost FROM treatments WHERE id = ?', (self.treatment_id,))
        data = self.parent.cursor.fetchone()
        if data:
            fields = ['date', 'description', 'observations', 'cost']
            for field, value in zip(fields, data):
                if field in self.entries:
                    if isinstance(self.entries[field], tk.Text):
                        self.entries[field].insert(tk.END, value)
                    else:
                        self.entries[field].insert(0, value)

    def save(self):
        data = {field: entry.get("1.0", tk.END).strip() if isinstance(entry, tk.Text) else entry.get().strip() for field, entry in self.entries.items()}

        # Validaciones
        if not all([data['date'], data['description']]):
            messagebox.showwarning("Advertencia", "Fecha y descripción son obligatorios.")
            return
        
        try:
            datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            messagebox.showwarning("Advertencia", "El formato de fecha (YYYY-MM-DD) es inválido.")
            return

        if data['cost']:
            try:
                float(data['cost'])
            except ValueError:
                messagebox.showwarning("Advertencia", "El costo debe ser un valor numérico válido.")
                return

        if self.treatment_id:
            self.parent.cursor.execute('''
                UPDATE treatments SET date = ?, description = ?, observations = ?, cost = ?
                WHERE id = ?
            ''', (data['date'], data['description'], data['observations'], data['cost'], self.treatment_id))
        else:
            self.parent.cursor.execute('''
                INSERT INTO treatments (patient_id, date, description, observations, cost)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.parent.current_patient_id, data['date'], data['description'], data['observations'], data['cost']))
        
        self.parent.conn.commit()
        self.parent.load_treatments()
        self.destroy()

class MedicalHistoryDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent.root)
        self.parent = parent
        self.title(title)
        self.transient(parent.root)
        self.grab_set()

        self.entries = {}
        fields = ['allergies', 'medications', 'diseases', 'notes']
        labels = ['Alergias', 'Medicamentos', 'Enfermedades', 'Notas']

        for label, field in zip(labels, fields):
            row = ttk.Frame(self)
            row.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            ttk.Label(row, text=label, width=25).pack(side=tk.LEFT)
            text_widget = tk.Text(row, height=3, width=30)
            text_widget.pack(side=tk.RIGHT, expand=True, fill=tk.X)
            self.entries[field] = text_widget
        
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="Guardar", command=self.save).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancelar", command=self.destroy).pack(side='left', padx=5)

        self.load_data()

    def load_data(self):
        self.parent.cursor.execute('SELECT allergies, medications, diseases, notes FROM medical_history WHERE patient_id = ?', (self.parent.current_patient_id,))
        data = self.parent.cursor.fetchone()
        if data:
            fields = ['allergies', 'medications', 'diseases', 'notes']
            for field, value in zip(fields, data):
                if value and field in self.entries:
                    self.entries[field].insert(tk.END, value)

    def save(self):
        data = {field: entry.get("1.0", tk.END).strip() for field, entry in self.entries.items()}
        self.parent.cursor.execute('SELECT * FROM medical_history WHERE patient_id = ?', (self.parent.current_patient_id,))
        if self.parent.cursor.fetchone():
            self.parent.cursor.execute('''
                UPDATE medical_history SET allergies = ?, medications = ?, diseases = ?, notes = ?
                WHERE patient_id = ?
            ''', (data['allergies'], data['medications'], data['diseases'], data['notes'], self.parent.current_patient_id))
        else:
            self.parent.cursor.execute('''
                INSERT INTO medical_history (patient_id, allergies, medications, diseases, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.parent.current_patient_id, data['allergies'], data['medications'], data['diseases'], data['notes']))
        
        self.parent.conn.commit()
        self.parent.load_medical_history()
        self.destroy()

if __name__ == '__main__':
    app = DentalManagementSystem()
    app.root.mainloop()