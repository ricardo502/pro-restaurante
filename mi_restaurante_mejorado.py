import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_DISPONIBLE = True
except ImportError:
    MATPLOTLIB_DISPONIBLE = False


NOMBRE_RESTAURANTE = "Restaurante Ricardo"
IMPUESTO = 0.07  
SIMBOLO_MONEDA = "$"


RUTA_BASE_DATOS = Path(__file__).resolve().with_name("restaurante.db")


PRODUCTOS_INICIALES = [
    ("Pollo", "Comida", 1.32),
    ("Cordero", "Comida", 1.65),
    ("Salmon", "Comida", 2.31),
    ("Merluza", "Comida", 3.22),
    ("Kebab", "Comida", 1.22),
    ("Pizza 1", "Comida", 1.99),
    ("Pizza 2", "Comida", 2.05),
    ("Pizza 3", "Comida", 2.65),
    ("Agua", "Bebida", 0.25),
    ("Soda", "Bebida", 0.99),
    ("Jugo", "Bebida", 1.21),
    ("Cola", "Bebida", 1.54),
    ("Vino 1", "Bebida", 1.08),
    ("Vino 2", "Bebida", 1.10),
    ("Cerveza 1", "Bebida", 2.00),
    ("Cerveza 2", "Bebida", 1.58),
    ("Helado", "Postre", 1.54),
    ("Fruta", "Postre", 1.68),
    ("Brownies", "Postre", 1.32),
    ("Flan", "Postre", 1.97),
    ("Mousse", "Postre", 2.55),
    ("Pastel 1", "Postre", 2.14),
    ("Pastel 2", "Postre", 1.94),
    ("Pastel 3", "Postre", 1.74),
]


def dinero(valor):

    return f"{SIMBOLO_MONEDA} {valor:,.2f}"


class BaseDatos:


    def __init__(self, ruta):
        self.ruta = ruta
        self.crear_tablas()
        self.cargar_productos_iniciales()

    def conectar(self):

        conexion = sqlite3.connect(self.ruta)
        conexion.row_factory = sqlite3.Row
        return conexion

    def crear_tablas(self):

        with self.conectar() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    categoria TEXT NOT NULL,
                    precio REAL NOT NULL CHECK(precio >= 0),
                    activo INTEGER NOT NULL DEFAULT 1
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    impuesto REAL NOT NULL,
                    total REAL NOT NULL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS detalle_ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venta_id INTEGER NOT NULL,
                    producto_id INTEGER,
                    producto_nombre TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio_unitario REAL NOT NULL,
                    importe REAL NOT NULL,
                    FOREIGN KEY (venta_id) REFERENCES ventas(id)
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_detalle_venta ON detalle_ventas(venta_id)")

    def cargar_productos_iniciales(self):

        with self.conectar() as con:
            cantidad = con.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
            if cantidad == 0:
                con.executemany(
                    "INSERT INTO productos(nombre, categoria, precio) VALUES (?, ?, ?)",
                    PRODUCTOS_INICIALES
                )

    def obtener_productos(self, incluir_inactivos=False):

        with self.conectar() as con:
            if incluir_inactivos:
                return con.execute(
                    "SELECT * FROM productos ORDER BY categoria, nombre"
                ).fetchall()
            return con.execute(
                "SELECT * FROM productos WHERE activo=1 ORDER BY categoria, nombre"
            ).fetchall()

    def guardar_producto(self, producto_id, nombre, categoria, precio):

        with self.conectar() as con:
            if producto_id:
                con.execute("""
                    UPDATE productos
                    SET nombre=?, categoria=?, precio=?
                    WHERE id=?
                """, (nombre, categoria, precio, producto_id))
            else:
                con.execute("""
                    INSERT INTO productos(nombre, categoria, precio)
                    VALUES (?, ?, ?)
                """, (nombre, categoria, precio))

    def desactivar_producto(self, producto_id):

        with self.conectar() as con:
            con.execute("UPDATE productos SET activo=0 WHERE id=?", (producto_id,))

    def registrar_venta(self, carrito):

        subtotal = sum(item["cantidad"] * item["precio"] for item in carrito.values())
        impuesto = round(subtotal * IMPUESTO, 2)
        total = round(subtotal + impuesto, 2)
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.conectar() as con:
            cursor = con.execute("""
                INSERT INTO ventas(fecha, subtotal, impuesto, total)
                VALUES (?, ?, ?, ?)
            """, (fecha, subtotal, impuesto, total))
            venta_id = cursor.lastrowid

            for producto_id, item in carrito.items():
                importe = item["cantidad"] * item["precio"]
                con.execute("""
                    INSERT INTO detalle_ventas(
                        venta_id, producto_id, producto_nombre, categoria,
                        cantidad, precio_unitario, importe
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    venta_id, producto_id, item["nombre"], item["categoria"],
                    item["cantidad"], item["precio"], importe
                ))

        return venta_id, fecha, subtotal, impuesto, total

    def obtener_ventas(self, limite=500):

        with self.conectar() as con:
            return con.execute("""
                SELECT id, fecha, subtotal, impuesto, total
                FROM ventas
                ORDER BY id DESC
                LIMIT ?
            """, (limite,)).fetchall()

    def obtener_detalle_venta(self, venta_id):

        with self.conectar() as con:
            return con.execute("""
                SELECT producto_nombre, categoria, cantidad,
                       precio_unitario, importe
                FROM detalle_ventas
                WHERE venta_id=?
                ORDER BY id
            """, (venta_id,)).fetchall()

    def ingresos_totales(self):

        with self.conectar() as con:
            return con.execute(
                "SELECT COALESCE(SUM(total), 0) FROM ventas"
            ).fetchone()[0]

    def datos_ventas_por_dia(self):
        with self.conectar() as con:
            return con.execute("""
                SELECT date(fecha) AS periodo, SUM(total) AS importe
                FROM ventas
                GROUP BY date(fecha)
                ORDER BY periodo
            """).fetchall()

    def datos_ventas_por_mes(self):
        with self.conectar() as con:
            return con.execute("""
                SELECT strftime('%Y-%m', fecha) AS periodo, SUM(total) AS importe
                FROM ventas
                GROUP BY strftime('%Y-%m', fecha)
                ORDER BY periodo
            """).fetchall()

    def datos_productos_mas_vendidos(self):
        with self.conectar() as con:
            return con.execute("""
                SELECT producto_nombre AS nombre, SUM(cantidad) AS cantidad
                FROM detalle_ventas
                GROUP BY producto_nombre
                ORDER BY cantidad DESC
                LIMIT 10
            """).fetchall()

    def datos_ingresos_categoria(self):
        with self.conectar() as con:
            return con.execute("""
                SELECT categoria, SUM(importe) AS importe
                FROM detalle_ventas
                GROUP BY categoria
                ORDER BY importe DESC
            """).fetchall()


class RestauranteApp:


    def __init__(self, ventana):
        self.ventana = ventana
        self.db = BaseDatos(RUTA_BASE_DATOS)
        self.carrito = {}
        self.venta_actual_id = None
        self.producto_seleccionado_id = None

        self.configurar_ventana()
        self.crear_estilos()
        self.crear_interfaz()
        self.actualizar_productos()
        self.actualizar_historial()
        self.actualizar_reportes()

    def configurar_ventana(self):
        self.ventana.title(f"{NOMBRE_RESTAURANTE} - Sistema de gestion")
        self.ventana.geometry("1280x780")
        self.ventana.minsize(1050, 680)
        self.ventana.configure(bg="#D6EAF8")

    def crear_estilos(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TNotebook", background="#D6EAF8", borderwidth=0)
        estilo.configure("TNotebook.Tab", padding=(16, 9), font=("Arial", 10, "bold"))
        estilo.configure("Treeview", rowheight=27, font=("Arial", 10))
        estilo.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        estilo.configure("TButton", padding=7, font=("Arial", 10, "bold"))
        estilo.configure("Titulo.TLabel", font=("Arial", 22, "bold"),
                         foreground="#40545A", background="#D6EAF8")
        estilo.configure("Subtitulo.TLabel", font=("Arial", 12, "bold"),
                         foreground="#40545A", background="#D6EAF8")

    def crear_interfaz(self):
        encabezado = tk.Frame(self.ventana, bg="#D6EAF8")
        encabezado.pack(fill="x", padx=18, pady=(12, 5))

        tk.Label(
            encabezado, text=NOMBRE_RESTAURANTE,
            font=("Arial", 25, "bold"), fg="#40545A", bg="#D6EAF8"
        ).pack(side="left")

        tk.Label(
            encabezado, text="Sistema de ventas y administracion",
            font=("Arial", 10), fg="#415A77", bg="#D6EAF8"
        ).pack(side="right", pady=12)

        self.pestanas = ttk.Notebook(self.ventana)
        self.pestanas.pack(fill="both", expand=True, padx=15, pady=10)

        self.tab_venta = tk.Frame(self.pestanas, bg="#F4F8FC")
        self.tab_productos = tk.Frame(self.pestanas, bg="#F4F8FC")
        self.tab_historial = tk.Frame(self.pestanas, bg="#F4F8FC")
        self.tab_reportes = tk.Frame(self.pestanas, bg="#F4F8FC")

        self.pestanas.add(self.tab_venta, text="  Ventas  ")
        self.pestanas.add(self.tab_productos, text="  Productos  ")
        self.pestanas.add(self.tab_historial, text="  Historial  ")
        self.pestanas.add(self.tab_reportes, text="  Reportes graficos  ")

        self.crear_pestana_ventas()
        self.crear_pestana_productos()
        self.crear_pestana_historial()
        self.crear_pestana_reportes()


    def crear_pestana_ventas(self):
        marco = self.tab_venta
        tk.Label(marco, text="Registro de venta", font=("Arial", 17, "bold"),
                 bg="#F4F8FC", fg="#40545A").pack(anchor="w", padx=15, pady=12)

        controles = tk.Frame(marco, bg="#F4F8FC")
        controles.pack(fill="x", padx=15)

        tk.Label(controles, text="Producto:", bg="#F4F8FC").grid(row=0, column=0, padx=5)
        self.combo_producto = ttk.Combobox(controles, state="readonly", width=38)
        self.combo_producto.grid(row=0, column=1, padx=5, pady=8)

        tk.Label(controles, text="Cantidad:", bg="#F4F8FC").grid(row=0, column=2, padx=5)
        self.spin_cantidad = tk.Spinbox(controles, from_=1, to=999, width=7)
        self.spin_cantidad.grid(row=0, column=3, padx=5)

        ttk.Button(controles, text="Agregar al pedido",
                   command=self.agregar_al_carrito).grid(row=0, column=4, padx=10)

        zona = tk.Frame(marco, bg="#F4F8FC")
        zona.pack(fill="both", expand=True, padx=15, pady=8)

        marco_tabla = tk.LabelFrame(zona, text="Productos de la cuenta",
                                    bg="#F4F8FC", padx=8, pady=8)
        marco_tabla.pack(side="left", fill="both", expand=True, padx=(0, 8))

        columnas = ("producto", "categoria", "cantidad", "precio", "importe")
        self.tabla_carrito = ttk.Treeview(
            marco_tabla, columns=columnas, show="headings", height=14
        )
        encabezados = {
            "producto": "Producto", "categoria": "Categoria",
            "cantidad": "Cantidad", "precio": "Precio unitario", "importe": "Importe"
        }
        anchos = {"producto": 190, "categoria": 100, "cantidad": 75,
                  "precio": 110, "importe": 110}
        for col in columnas:
            self.tabla_carrito.heading(col, text=encabezados[col])
            self.tabla_carrito.column(col, width=anchos[col], anchor="center")
        self.tabla_carrito.pack(fill="both", expand=True)

        panel_derecho = tk.Frame(zona, bg="#E1ECF7", padx=15, pady=12)
        panel_derecho.pack(side="right", fill="y")

        tk.Label(panel_derecho, text="Resumen de cuenta",
                 font=("Arial", 14, "bold"), bg="#E1ECF7",
                 fg="#40545A").pack(pady=(4, 18))

        self.lbl_subtotal = tk.Label(panel_derecho, text="Subtotal: $ 0.00",
                                     font=("Arial", 11), bg="#E1ECF7")
        self.lbl_subtotal.pack(anchor="w", pady=6)
        self.lbl_impuesto = tk.Label(panel_derecho, text="Impuesto (7 %): $ 0.00",
                                     font=("Arial", 11), bg="#E1ECF7")
        self.lbl_impuesto.pack(anchor="w", pady=6)
        self.lbl_total = tk.Label(panel_derecho, text="TOTAL: $ 0.00",
                                  font=("Arial", 15, "bold"), bg="#E1ECF7",
                                  fg="#155A91")
        self.lbl_total.pack(anchor="w", pady=12)

        ttk.Button(panel_derecho, text="Quitar producto",
                   command=self.quitar_del_carrito).pack(fill="x", pady=5)
        ttk.Button(panel_derecho, text="Vaciar cuenta",
                   command=self.vaciar_carrito).pack(fill="x", pady=5)
        ttk.Button(panel_derecho, text="FINALIZAR Y GUARDAR VENTA",
                   command=self.finalizar_venta).pack(fill="x", pady=(18, 5))

        self.texto_recibo = tk.Text(marco, height=8, font=("Courier New", 9),
                                    wrap="none", bg="white")
        self.texto_recibo.pack(fill="x", padx=15, pady=(3, 12))
        self.texto_recibo.insert("1.0", "El recibo de la venta aparecera aqui.")

    def actualizar_productos_combo(self):
        self.productos_combo = self.db.obtener_productos()
        self.mapa_combo = {}
        opciones = []
        for p in self.productos_combo:
            etiqueta = f'{p["nombre"]} | {p["categoria"]} | {dinero(p["precio"])}'
            opciones.append(etiqueta)
            self.mapa_combo[etiqueta] = p
        self.combo_producto["values"] = opciones
        if opciones:
            self.combo_producto.current(0)
        else:
            self.combo_producto.set("")

    def agregar_al_carrito(self):
        seleccion = self.combo_producto.get()
        if not seleccion or seleccion not in self.mapa_combo:
            messagebox.showwarning("Producto", "Selecciona un producto.")
            return
        try:
            cantidad = int(self.spin_cantidad.get())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Cantidad", "Escribe una cantidad entera mayor que cero.")
            return

        producto = self.mapa_combo[seleccion]
        pid = producto["id"]
        if pid not in self.carrito:
            self.carrito[pid] = {
                "nombre": producto["nombre"],
                "categoria": producto["categoria"],
                "precio": float(producto["precio"]),
                "cantidad": 0
            }
        self.carrito[pid]["cantidad"] += cantidad
        self.refrescar_carrito()

    def refrescar_carrito(self):
        for fila in self.tabla_carrito.get_children():
            self.tabla_carrito.delete(fila)

        subtotal = 0
        for pid, item in self.carrito.items():
            importe = item["cantidad"] * item["precio"]
            subtotal += importe
            self.tabla_carrito.insert("", "end", iid=str(pid), values=(
                item["nombre"], item["categoria"], item["cantidad"],
                dinero(item["precio"]), dinero(importe)
            ))

        impuesto = round(subtotal * IMPUESTO, 2)
        total = round(subtotal + impuesto, 2)
        self.lbl_subtotal.config(text=f"Subtotal: {dinero(subtotal)}")
        self.lbl_impuesto.config(text=f"Impuesto ({IMPUESTO:.0%}): {dinero(impuesto)}")
        self.lbl_total.config(text=f"TOTAL: {dinero(total)}")

    def quitar_del_carrito(self):
        seleccion = self.tabla_carrito.selection()
        if not seleccion:
            messagebox.showinfo("Pedido", "Selecciona un producto de la cuenta.")
            return
        pid = int(seleccion[0])
        self.carrito.pop(pid, None)
        self.refrescar_carrito()

    def vaciar_carrito(self):
        if self.carrito and not messagebox.askyesno(
            "Confirmar", "¿Deseas vaciar todos los productos de la cuenta?"
        ):
            return
        self.carrito.clear()
        self.refrescar_carrito()

    def finalizar_venta(self):
        if not self.carrito:
            messagebox.showwarning("Venta", "Agrega al menos un producto.")
            return
        if not messagebox.askyesno("Confirmar venta", "¿Deseas guardar esta venta?"):
            return

        try:
            venta_id, fecha, subtotal, impuesto, total = self.db.registrar_venta(self.carrito)
        except sqlite3.Error as error:
            messagebox.showerror("Base de datos", f"No se pudo guardar la venta:\n{error}")
            return

        lineas = [
            f"{NOMBRE_RESTAURANTE}",
            f"Recibo de venta No. {venta_id}",
            f"Fecha: {fecha}",
            "-" * 48,
            f"{'Producto':20} {'Cant.':>5} {'Importe':>12}",
            "-" * 48
        ]
        for item in self.carrito.values():
            importe = item["cantidad"] * item["precio"]
            lineas.append(
                f"{item['nombre'][:20]:20} {item['cantidad']:>5} {dinero(importe):>12}"
            )
        lineas.extend([
            "-" * 48,
            f"Subtotal: {dinero(subtotal)}",
            f"Impuesto ({IMPUESTO:.0%}): {dinero(impuesto)}",
            f"TOTAL: {dinero(total)}",
            "",
            "Gracias por su visita."
        ])
        recibo = "\n".join(lineas)
        self.texto_recibo.delete("1.0", "end")
        self.texto_recibo.insert("1.0", recibo)

        self.venta_actual_id = venta_id
        self.carrito.clear()
        self.refrescar_carrito()
        self.actualizar_historial()
        self.actualizar_reportes()
        messagebox.showinfo(
            "Venta guardada",
            f"La venta #{venta_id} se guardo correctamente.\nTotal: {dinero(total)}"
        )


    def crear_pestana_productos(self):
        marco = self.tab_productos
        tk.Label(marco, text="Administracion de productos",
                 font=("Arial", 17, "bold"), bg="#F4F8FC",
                 fg="#40545A").pack(anchor="w", padx=15, pady=12)

        formulario = tk.LabelFrame(marco, text="Datos del producto",
                                   bg="#F4F8FC", padx=12, pady=12)
        formulario.pack(fill="x", padx=15, pady=5)

        tk.Label(formulario, text="Nombre:", bg="#F4F8FC").grid(row=0, column=0, padx=5)
        self.entry_nombre = ttk.Entry(formulario, width=25)
        self.entry_nombre.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(formulario, text="Categoria:", bg="#F4F8FC").grid(row=0, column=2, padx=5)
        self.combo_categoria = ttk.Combobox(
            formulario, values=["Comida", "Bebida", "Postre"], state="readonly", width=17
        )
        self.combo_categoria.grid(row=0, column=3, padx=5)
        self.combo_categoria.current(0)

        tk.Label(formulario, text="Precio:", bg="#F4F8FC").grid(row=0, column=4, padx=5)
        self.entry_precio = ttk.Entry(formulario, width=12)
        self.entry_precio.grid(row=0, column=5, padx=5)

        ttk.Button(formulario, text="Guardar producto",
                   command=self.guardar_producto).grid(row=0, column=6, padx=8)
        ttk.Button(formulario, text="Limpiar",
                   command=self.limpiar_formulario_producto).grid(row=0, column=7, padx=4)

        columnas = ("id", "nombre", "categoria", "precio", "estado")
        self.tabla_productos = ttk.Treeview(
            marco, columns=columnas, show="headings", height=17
        )
        for col, titulo, ancho in [
            ("id", "ID", 60), ("nombre", "Nombre", 260),
            ("categoria", "Categoria", 160), ("precio", "Precio", 130),
            ("estado", "Estado", 100)
        ]:
            self.tabla_productos.heading(col, text=titulo)
            self.tabla_productos.column(col, width=ancho, anchor="center")
        self.tabla_productos.pack(fill="both", expand=True, padx=15, pady=10)
        self.tabla_productos.bind("<<TreeviewSelect>>", self.seleccionar_producto)

        acciones = tk.Frame(marco, bg="#F4F8FC")
        acciones.pack(fill="x", padx=15, pady=(0, 12))
        ttk.Button(acciones, text="Actualizar lista",
                   command=self.actualizar_productos).pack(side="left", padx=4)
        ttk.Button(acciones, text="Desactivar producto seleccionado",
                   command=self.eliminar_producto).pack(side="left", padx=4)

    def actualizar_productos(self):
        if not hasattr(self, "tabla_productos"):
            return
        for fila in self.tabla_productos.get_children():
            self.tabla_productos.delete(fila)
        for p in self.db.obtener_productos(incluir_inactivos=True):
            estado = "Activo" if p["activo"] else "Inactivo"
            self.tabla_productos.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["nombre"], p["categoria"], dinero(p["precio"]), estado
            ))
        if hasattr(self, "combo_producto"):
            self.actualizar_productos_combo()

    def seleccionar_producto(self, _evento=None):
        seleccion = self.tabla_productos.selection()
        if not seleccion:
            return
        pid = int(seleccion[0])
        producto = next(
            (p for p in self.db.obtener_productos(incluir_inactivos=True) if p["id"] == pid),
            None
        )
        if producto is None:
            return
        self.producto_seleccionado_id = pid
        self.entry_nombre.delete(0, "end")
        self.entry_nombre.insert(0, producto["nombre"])
        self.combo_categoria.set(producto["categoria"])
        self.entry_precio.delete(0, "end")
        self.entry_precio.insert(0, str(producto["precio"]))

    def limpiar_formulario_producto(self):
        self.producto_seleccionado_id = None
        self.entry_nombre.delete(0, "end")
        self.entry_precio.delete(0, "end")
        self.combo_categoria.current(0)
        self.tabla_productos.selection_remove(self.tabla_productos.selection())

    def guardar_producto(self):
        nombre = self.entry_nombre.get().strip()
        categoria = self.combo_categoria.get().strip()
        try:
            precio = float(self.entry_precio.get().replace(",", "."))
            if precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Precio", "Escribe un precio numerico igual o mayor que cero.")
            return
        if not nombre:
            messagebox.showwarning("Producto", "Escribe el nombre del producto.")
            return
        if categoria not in ("Comida", "Bebida", "Postre"):
            messagebox.showwarning("Categoria", "Selecciona una categoria valida.")
            return

        try:
            self.db.guardar_producto(self.producto_seleccionado_id, nombre, categoria, precio)
        except sqlite3.IntegrityError:
            messagebox.showerror("Producto", "Ya existe un producto con ese nombre.")
            return
        except sqlite3.Error as error:
            messagebox.showerror("Base de datos", str(error))
            return

        self.limpiar_formulario_producto()
        self.actualizar_productos()
        messagebox.showinfo("Productos", "El producto se guardo correctamente.")

    def eliminar_producto(self):
        seleccion = self.tabla_productos.selection()
        if not seleccion:
            messagebox.showwarning("Productos", "Selecciona un producto.")
            return
        pid = int(seleccion[0])
        if not messagebox.askyesno(
            "Confirmar", "El producto se desactivara y ya no aparecera en nuevas ventas."
        ):
            return
        self.db.desactivar_producto(pid)
        self.limpiar_formulario_producto()
        self.actualizar_productos()
        messagebox.showinfo("Productos", "Producto desactivado.")


    def crear_pestana_historial(self):
        marco = self.tab_historial
        tk.Label(marco, text="Historial de ventas",
                 font=("Arial", 17, "bold"), bg="#F4F8FC",
                 fg="#40545A").pack(anchor="w", padx=15, pady=12)

        columnas = ("id", "fecha", "subtotal", "impuesto", "total")
        self.tabla_historial = ttk.Treeview(
            marco, columns=columnas, show="headings", height=15
        )
        for col, titulo, ancho in [
            ("id", "Folio", 80), ("fecha", "Fecha y hora", 220),
            ("subtotal", "Subtotal", 150), ("impuesto", "Impuesto", 150),
            ("total", "Total", 150)
        ]:
            self.tabla_historial.heading(col, text=titulo)
            self.tabla_historial.column(col, width=ancho, anchor="center")
        self.tabla_historial.pack(fill="both", expand=True, padx=15, pady=8)
        self.tabla_historial.bind("<<TreeviewSelect>>", self.mostrar_detalle_historial)

        ttk.Button(marco, text="Actualizar historial",
                   command=self.actualizar_historial).pack(anchor="w", padx=15, pady=5)

        self.detalle_historial = tk.Text(marco, height=9, font=("Courier New", 9))
        self.detalle_historial.pack(fill="x", padx=15, pady=8)

    def actualizar_historial(self):
        if not hasattr(self, "tabla_historial"):
            return
        for fila in self.tabla_historial.get_children():
            self.tabla_historial.delete(fila)
        for venta in self.db.obtener_ventas():
            self.tabla_historial.insert("", "end", iid=str(venta["id"]), values=(
                venta["id"], venta["fecha"], dinero(venta["subtotal"]),
                dinero(venta["impuesto"]), dinero(venta["total"])
            ))

    def mostrar_detalle_historial(self, _evento=None):
        seleccion = self.tabla_historial.selection()
        if not seleccion:
            return
        venta_id = int(seleccion[0])
        detalles = self.db.obtener_detalle_venta(venta_id)
        self.detalle_historial.delete("1.0", "end")
        self.detalle_historial.insert("end", f"DETALLE DE LA VENTA #{venta_id}\n")
        self.detalle_historial.insert("end", "-" * 65 + "\n")
        for item in detalles:
            self.detalle_historial.insert(
                "end",
                f'{item["producto_nombre"]} | {item["categoria"]} | '
                f'{item["cantidad"]} x {dinero(item["precio_unitario"])} = '
                f'{dinero(item["importe"])}\n'
            )


    def crear_pestana_reportes(self):
        marco = self.tab_reportes
        tk.Label(marco, text="Reportes y estadisticas",
                 font=("Arial", 17, "bold"), bg="#F4F8FC",
                 fg="#40545A").pack(anchor="w", padx=15, pady=12)

        resumen = tk.Frame(marco, bg="#E1ECF7", padx=15, pady=12)
        resumen.pack(fill="x", padx=15, pady=5)

        self.lbl_ingresos_totales = tk.Label(
            resumen, text="Ingresos totales: $ 0.00",
            font=("Arial", 17, "bold"), fg="#40545A", bg="#E1ECF7"
        )
        self.lbl_ingresos_totales.pack(side="left", padx=10)

        self.lbl_num_ventas = tk.Label(
            resumen, text="Ventas registradas: 0",
            font=("Arial", 12, "bold"), bg="#E1ECF7"
        )
        self.lbl_num_ventas.pack(side="right", padx=10)

        barra = tk.Frame(marco, bg="#F4F8FC")
        barra.pack(fill="x", padx=15, pady=8)
        tk.Label(barra, text="Tipo de reporte:", bg="#F4F8FC").pack(side="left")
        self.combo_reporte = ttk.Combobox(
            barra, state="readonly", width=32,
            values=[
                "Ventas por dia",
                "Productos mas vendidos",
                "Ingresos por categoria",
                "Ventas por mes"
            ]
        )
        self.combo_reporte.pack(side="left", padx=8)
        self.combo_reporte.current(0)
        ttk.Button(barra, text="Mostrar grafica",
                   command=self.dibujar_grafica).pack(side="left", padx=5)
        ttk.Button(barra, text="Actualizar reportes",
                   command=self.actualizar_reportes).pack(side="left", padx=5)

        self.marco_grafica = tk.Frame(marco, bg="white")
        self.marco_grafica.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if not MATPLOTLIB_DISPONIBLE:
            tk.Label(
                self.marco_grafica,
                text="Para mostrar las graficas instala Matplotlib:\n"
                     "python -m pip install matplotlib",
                font=("Arial", 13), bg="white", fg="#155A91"
            ).pack(expand=True)
        else:
            self.figura = Figure(figsize=(9, 4.5), dpi=100)
            self.ejes = self.figura.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.figura, master=self.marco_grafica)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            self.dibujar_grafica()

    def actualizar_reportes(self):
        total = self.db.ingresos_totales()
        ventas = self.db.obtener_ventas(limite=100000)
        if hasattr(self, "lbl_ingresos_totales"):
            self.lbl_ingresos_totales.config(
                text=f"Ingresos totales: {dinero(total)}"
            )
            self.lbl_num_ventas.config(text=f"Ventas registradas: {len(ventas)}")
        if MATPLOTLIB_DISPONIBLE and hasattr(self, "canvas"):
            self.dibujar_grafica()

    def dibujar_grafica(self):
        if not MATPLOTLIB_DISPONIBLE or not hasattr(self, "ejes"):
            return

        tipo = self.combo_reporte.get()
        self.ejes.clear()
        self.figura.patch.set_facecolor("white")
        self.ejes.set_facecolor("#FAFAFA")

        if tipo == "Ventas por dia":
            datos = self.db.datos_ventas_por_dia()
            etiquetas = [fila["periodo"] for fila in datos]
            valores = [fila["importe"] for fila in datos]
            self.ejes.bar(etiquetas, valores)
            self.ejes.set_title("Ingresos por dia")
            self.ejes.set_ylabel("Importe")
            self.ejes.set_xlabel("Fecha")
            self.ejes.tick_params(axis="x", rotation=40)

        elif tipo == "Productos mas vendidos":
            datos = self.db.datos_productos_mas_vendidos()
            etiquetas = [fila["nombre"] for fila in datos]
            valores = [fila["cantidad"] for fila in datos]
            self.ejes.barh(etiquetas[::-1], valores[::-1])
            self.ejes.set_title("Los 10 productos mas vendidos")
            self.ejes.set_xlabel("Unidades vendidas")

        elif tipo == "Ingresos por categoria":
            datos = self.db.datos_ingresos_categoria()
            etiquetas = [fila["categoria"] for fila in datos]
            valores = [fila["importe"] for fila in datos]
            if valores:
                self.ejes.pie(
                    valores, labels=etiquetas, autopct="%1.1f%%",
                    startangle=90
                )
                self.ejes.set_title("Distribucion de ingresos por categoria")
                self.ejes.axis("equal")
            else:
                self.ejes.text(0.5, 0.5, "Todavia no hay ventas registradas",
                               ha="center", va="center", transform=self.ejes.transAxes)

        elif tipo == "Ventas por mes":
            datos = self.db.datos_ventas_por_mes()
            etiquetas = [fila["periodo"] for fila in datos]
            valores = [fila["importe"] for fila in datos]
            self.ejes.bar(etiquetas, valores)
            self.ejes.set_title("Ingresos por mes")
            self.ejes.set_ylabel("Importe")
            self.ejes.set_xlabel("Mes")
            self.ejes.tick_params(axis="x", rotation=35)

        if tipo != "Ingresos por categoria" and not (
            self.db.datos_ventas_por_dia() if tipo == "Ventas por dia"
            else self.db.datos_productos_mas_vendidos() if tipo == "Productos mas vendidos"
            else self.db.datos_ventas_por_mes()
        ):
            self.ejes.text(0.5, 0.5, "Todavia no hay ventas registradas",
                           ha="center", va="center", transform=self.ejes.transAxes)

        self.figura.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    ventana_principal = tk.Tk()
    aplicacion = RestauranteApp(ventana_principal)
    ventana_principal.mainloop()
