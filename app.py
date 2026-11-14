import os
import json
import sqlite3

from functools import wraps
from flask import (
    Flask, request, redirect, url_for,
    session, flash, jsonify, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# 1. CẤU HÌNH WEBSITE
# ==========================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "class-portal-local-development-key"
)

DATABASE = "class_portal.db"

PERMISSIONS = {
    "seating": "Sơ đồ lớp",
    "students": "Danh sách học sinh",
    "timetable": "Thời khóa biểu",
    "teachers": "Danh bạ giáo viên",
    "announcements": "Thông báo"
}


# ==========================================
# 2. KẾT NỐI VÀ TẠO CƠ SỞ DỮ LIỆU
# ==========================================

def connect_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = connect_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            permissions TEXT NOT NULL DEFAULT '{}'
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            group_name TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            show_phone INTEGER DEFAULT 0
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            period TEXT NOT NULL,
            subject TEXT NOT NULL,
            teacher TEXT DEFAULT '',
            room TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS seating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL DEFAULT '[]'
        )
    """)

    # Tạo tài khoản quản trị viên lần đầu
    admin = db.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:
        db.execute("""
            INSERT INTO users (username, password, role, permissions)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("admin12345"),
            "admin",
            json.dumps({key: True for key in PERMISSIONS})
        ))

    db.commit()
    db.close()


# ==========================================
# 3. KIỂM TRA ĐĂNG NHẬP VÀ QUYỀN
# ==========================================

def current_user():
    if "user_id" not in session:
        return None

    db = connect_db()
    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    db.close()

    return user


def has_permission(permission):
    user = current_user()

    if not user:
        return False

    if user["role"] == "admin":
        return True

    try:
        permissions = json.loads(user["permissions"])
    except (TypeError, json.JSONDecodeError):
        permissions = {}

    return permissions.get(permission, False)


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def permission_required(permission):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if not current_user():
                return redirect(url_for("login"))

            if not has_permission(permission):
                return "Bạn không có quyền thực hiện chức năng này.", 403

            return function(*args, **kwargs)

        return wrapper

    return decorator


# ==========================================
# 4. GIAO DIỆN DÙNG CHUNG
# ==========================================

PAGE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - CLASS PORTAL</title>
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
}

header {
    background: #14243d;
    color: white;
    padding: 18px 5%;
}

header h2 { margin: 0; }

nav {
    display: flex;
    gap: 9px;
    flex-wrap: wrap;
    margin-top: 15px;
}

nav a {
    color: white;
    text-decoration: none;
    background: #263b59;
    padding: 10px 13px;
    border-radius: 8px;
}

main {
    max-width: 1100px;
    margin: 25px auto;
    padding: 0 15px;
}

.panel {
    background: white;
    border-radius: 13px;
    padding: 20px;
    margin-bottom: 18px;
    border: 1px solid #e2e8f0;
}

button, .btn {
    border: 0;
    background: #1769d2;
    color: white;
    padding: 10px 14px;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
}

input, select, textarea {
    width: 100%;
    padding: 11px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin: 6px 0 13px;
}

label { font-weight: bold; }

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
}

td, th {
    border-bottom: 1px solid #e2e8f0;
    padding: 12px;
    text-align: left;
}

th { background: #f1f5f9; }

.muted { color: #64748b; }

.message {
    background: #e7f7ed;
    color: #17683b;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 12px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
}

.card {
    background: #edf4ff;
    border-radius: 10px;
    padding: 18px;
}

#stage {
    position: relative;
    min-width: 650px;
    height: 550px;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    background-color: #fbfdff;
    background-image:
        linear-gradient(#e8edf4 1px, transparent 1px),
        linear-gradient(90deg, #e8edf4 1px, transparent 1px);
    background-size: 25px 25px;
}

.seat-item {
    position: absolute;
    min-width: 100px;
    min-height: 55px;
    padding: 10px;
    background: #dcecff;
    border: 2px solid #4775a8;
    border-radius: 9px;
    text-align: center;
    cursor: grab;
    user-select: none;
}

.seat-item.chair {
    background: #e7f6eb;
    border-color: #55a16d;
}

.seat-item.board {
    background: #26384e;
    color: white;
}

@media(max-width: 650px) {
    nav { gap: 5px; }
    nav a { font-size: 13px; }
}
</style>
</head>
<body>

<header>
    <h2>CLASS PORTAL</h2>
    <div>Hệ thống quản lý lớp học</div>

    {% if user %}
    <nav>
        <a href="{{ url_for('home') }}">Trang chủ</a>
        <a href="{{ url_for('students') }}">Học sinh</a>
        <a href="{{ url_for('teachers') }}">Giáo viên</a>
        <a href="{{ url_for('timetable_page') }}">Thời khóa biểu</a>
        <a href="{{ url_for('seating_page') }}">Sơ đồ lớp</a>
        <a href="{{ url_for('announcements_page') }}">Thông báo</a>

        {% if user['role'] == 'admin' %}
        <a href="{{ url_for('accounts') }}">Quản lý tài khoản</a>
        {% endif %}

        <a href="{{ url_for('logout') }}">Đăng xuất</a>
    </nav>
    {% endif %}
</header>

<main>
    {% for msg in get_flashed_messages() %}
        <div class="message">{{ msg }}</div>
    {% endfor %}

    <section class="panel">
        <h2>{{ title }}</h2>
        {{ content|safe }}
    </section>
</main>

</body>
</html>
"""


def render_page(title, content):
    return render_template_string(
        PAGE,
        title=title,
        content=content,
        user=current_user()
    )


# ==========================================
# 5. ĐĂNG NHẬP / ĐĂNG XUẤT
# ==========================================

@app.route("/", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = connect_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        flash("Tên đăng nhập hoặc mật khẩu không đúng.")

    content = """
    <h3>Đăng nhập hệ thống</h3>
    <form method="POST">
        <label>Tên đăng nhập</label>
        <input name="username" required>

        <label>Mật khẩu</label>
        <input name="password" type="password" required>

        <button type="submit">Đăng nhập</button>
    </form>
    <p class="muted">web test</p>
    """

    return render_page("Đăng nhập", content)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# 6. TRANG CHỦ
# ==========================================

@app.route("/home")
@login_required
def home():
    content = """
    <h3>Chào mừng đến với CLASS PORTAL!</h3>
    <p>Đây là hệ thống quản lý lớp học.</p>

    <div class="grid">
        <div class="card">
            <h3>Học sinh</h3>
            <p>Quản lý danh sách lớp.</p>
            <a class="btn" href="/students">Mở</a>
        </div>

        <div class="card">
            <h3>Thời khóa biểu</h3>
            <p>Xem lịch học trong tuần.</p>
            <a class="btn" href="/timetable">Mở</a>
        </div>

        <div class="card">
            <h3>Sơ đồ lớp</h3>
            <p>Sắp xếp bàn ghế và vị trí ngồi.</p>
            <a class="btn" href="/seating">Mở</a>
        </div>

        <div class="card">
            <h3>Danh bạ giáo viên</h3>
            <p>Thông tin liên hệ giáo viên.</p>
            <a class="btn" href="/teachers">Mở</a>
        </div>
    </div>
    """

    return render_page("Trang chủ", content)


# ==========================================
# 7. DANH SÁCH HỌC SINH
# ==========================================

@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    db = connect_db()

    if request.method == "POST":
        if not has_permission("students"):
            db.close()
            return "Bạn không có quyền thêm học sinh.", 403

        name = request.form.get("name", "").strip()
        group_name = request.form.get("group_name", "").strip()
        note = request.form.get("note", "").strip()

        if name:
            db.execute("""
                INSERT INTO students (name, group_name, note)
                VALUES (?, ?, ?)
            """, (name, group_name, note))
            db.commit()
            flash("Đã thêm học sinh.")

        db.close()
        return redirect(url_for("students"))

    rows = db.execute(
        "SELECT * FROM students ORDER BY name"
    ).fetchall()
    db.close()

    form = ""

    if has_permission("students"):
        form = """
        <h3>Thêm học sinh</h3>
        <form method="POST">
            <label>Họ và tên</label>
            <input name="name" required>

            <label>Tổ</label>
            <input name="group_name">

            <label>Ghi chú</label>
            <input name="note">

            <button>Thêm học sinh</button>
        </form>
        """

    table = """
    <h3>Danh sách học sinh</h3>
    <table>
        <tr><th>Họ tên</th><th>Tổ</th><th>Ghi chú</th></tr>
    """

    for row in rows:
        table += f"""
        <tr>
            <td>{row['name']}</td>
            <td>{row['group_name']}</td>
            <td>{row['note']}</td>
        </tr>
        """

    table += "</table>"

    return render_page("Danh sách học sinh", form + table)


# ==========================================
# 8. DANH BẠ GIÁO VIÊN
# ==========================================

@app.route("/teachers", methods=["GET", "POST"])
@login_required
def teachers():
    db = connect_db()

    if request.method == "POST":
        if not has_permission("teachers"):
            db.close()
            return "Bạn không có quyền thêm giáo viên.", 403

        name = request.form.get("name", "").strip()
        subject = request.form.get("subject", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        show_phone = 1 if request.form.get("show_phone") else 0

        if name:
            db.execute("""
                INSERT INTO teachers
                (name, subject, phone, email, show_phone)
                VALUES (?, ?, ?, ?, ?)
            """, (name, subject, phone, email, show_phone))
            db.commit()
            flash("Đã thêm giáo viên.")

        db.close()
        return redirect(url_for("teachers"))

    rows = db.execute(
        "SELECT * FROM teachers ORDER BY name"
    ).fetchall()
    db.close()

    form = ""

    if has_permission("teachers"):
        form = """
        <h3>Thêm giáo viên</h3>
        <form method="POST">
            <label>Họ tên</label>
            <input name="name" required>

            <label>Môn giảng dạy</label>
            <input name="subject">

            <label>Số điện thoại</label>
            <input name="phone">

            <label>Email</label>
            <input name="email">

            <label>
                <input type="checkbox" name="show_phone" value="1"
                       style="width:auto">
                Giáo viên đồng ý hiển thị số điện thoại
            </label>
            <br><br>
            <button>Thêm giáo viên</button>
        </form>
        """

    table = """
    <h3>Danh bạ giáo viên</h3>
    <table>
    <tr><th>Họ tên</th><th>Môn</th><th>Điện thoại</th><th>Email</th></tr>
    """

    for row in rows:
        phone = row["phone"] if row["show_phone"] else "Không công khai"
        table += f"""
        <tr>
            <td>{row['name']}</td>
            <td>{row['subject']}</td>
            <td>{phone}</td>
            <td>{row['email']}</td>
        </tr>
        """

    table += "</table>"

    return render_page("Danh bạ giáo viên", form + table)


# ==========================================
# 9. THỜI KHÓA BIỂU
# ==========================================

@app.route("/timetable", methods=["GET", "POST"])
@login_required
def timetable_page():
    db = connect_db()

    if request.method == "POST":
        if not has_permission("timetable"):
            db.close()
            return "Bạn không có quyền sửa thời khóa biểu.", 403

        day = request.form.get("day", "")
        period = request.form.get("period", "").strip()
        subject = request.form.get("subject", "").strip()
        teacher = request.form.get("teacher", "").strip()
        room = request.form.get("room", "").strip()

        if day and period and subject:
            db.execute("""
                INSERT INTO timetable
                (day, period, subject, teacher, room)
                VALUES (?, ?, ?, ?, ?)
            """, (day, period, subject, teacher, room))
            db.commit()
            flash("Đã thêm tiết học.")

        db.close()
        return redirect(url_for("timetable_page"))

    rows = db.execute("""
        SELECT * FROM timetable
        ORDER BY
        CASE day
            WHEN 'Thứ Hai' THEN 1
            WHEN 'Thứ Ba' THEN 2
            WHEN 'Thứ Tư' THEN 3
            WHEN 'Thứ Năm' THEN 4
            WHEN 'Thứ Sáu' THEN 5
            WHEN 'Thứ Bảy' THEN 6
        END,
        CAST(period AS INTEGER)
    """).fetchall()
    db.close()

    form = ""

    if has_permission("timetable"):
        form = """
        <h3>Thêm tiết học</h3>
        <form method="POST">
            <label>Ngày</label>
            <select name="day">
                <option>Thứ Hai</option>
                <option>Thứ Ba</option>
                <option>Thứ Tư</option>
                <option>Thứ Năm</option>
                <option>Thứ Sáu</option>
                <option>Thứ Bảy</option>
            </select>

            <label>Tiết</label>
            <input name="period" placeholder="Ví dụ: 1" required>

            <label>Môn học</label>
            <input name="subject" required>

            <label>Giáo viên</label>
            <input name="teacher">

            <label>Phòng học</label>
            <input name="room">

            <button>Thêm tiết học</button>
        </form>
        """

    table = """
    <h3>Thời khóa biểu</h3>
    <table>
    <tr>
        <th>Ngày</th><th>Tiết</th><th>Môn học</th>
        <th>Giáo viên</th><th>Phòng</th>
    </tr>
    """

    for row in rows:
        table += f"""
        <tr>
            <td>{row['day']}</td>
            <td>{row['period']}</td>
            <td>{row['subject']}</td>
            <td>{row['teacher']}</td>
            <td>{row['room']}</td>
        </tr>
        """

    table += "</table>"

    return render_page("Thời khóa biểu", form + table)


# ==========================================
# 10. THÔNG BÁO
# ==========================================

@app.route("/announcements", methods=["GET", "POST"])
@login_required
def announcements_page():
    db = connect_db()

    if request.method == "POST":
        if not has_permission("announcements"):
            db.close()
            return "Bạn không có quyền đăng thông báo.", 403

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if title and content:
            db.execute("""
                INSERT INTO announcements (title, content)
                VALUES (?, ?)
            """, (title, content))
            db.commit()
            flash("Đã đăng thông báo.")

        db.close()
        return redirect(url_for("announcements_page"))

    rows = db.execute(
        "SELECT * FROM announcements ORDER BY id DESC"
    ).fetchall()
    db.close()

    form = ""

    if has_permission("announcements"):
        form = """
        <h3>Đăng thông báo</h3>
        <form method="POST">
            <label>Tiêu đề</label>
            <input name="title" required>

            <label>Nội dung</label>
            <textarea name="content" rows="5" required></textarea>

            <button>Đăng thông báo</button>
        </form>
        """

    listing = "<h3>Bảng thông báo</h3>"

    for row in rows:
        listing += f"""
        <div class="card" style="margin:10px 0">
            <h3>{row['title']}</h3>
            <p>{row['content']}</p>
        </div>
        """

    return render_page("Thông báo", form + listing)


# ==========================================
# 11. SƠ ĐỒ LỚP
# ==========================================

@app.route("/seating")
@login_required
def seating_page():
    db = connect_db()

    saved = db.execute(
        "SELECT data FROM seating WHERE id = 1"
    ).fetchone()

    db.close()

    initial_data = saved["data"] if saved else "[]"

    can_edit = has_permission("seating")

    content = """
    <p>Kéo bàn ghế để sắp xếp vị trí. Nhấn đúp vào một vật dụng để đổi tên.</p>

    {% if can_edit %}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0">
        <button onclick="addItem('Bàn học sinh')">Thêm bàn</button>
        <button onclick="addItem('Ghế')">Thêm ghế</button>
        <button onclick="addItem('Bàn giáo viên')">Bàn giáo viên</button>
        <button onclick="addItem('Bảng lớp')">Bảng lớp</button>
        <button onclick="saveItems()">Lưu sơ đồ</button>
        <button onclick="deleteItem()">Xóa mục chọn</button>
    </div>
    {% endif %}

    <div style="overflow:auto">
        <div id="stage"></div>
    </div>

    <script>
    const stage = document.getElementById("stage");
    let items = INITIAL_DATA;
    let selected = null;
    const canEdit = CAN_EDIT;

    function draw() {
        stage.innerHTML = "";

        items.forEach((item, index) => {
            const el = document.createElement("div");
            el.className = "seat-item";

            if (item.type === "Ghế") el.classList.add("chair");
            if (item.type === "Bảng lớp") el.classList.add("board");

            el.style.left = item.x + "px";
            el.style.top = item.y + "px";
            el.textContent = item.name;

            el.onclick = () => {
                selected = index;
            };

            el.ondblclick = () => {
                if (!canEdit) return;
                const name = prompt("Nhập tên mới:", item.name);
                if (name !== null) {
                    item.name = name;
                    draw();
                }
            };

            if (canEdit) {
                el.onpointerdown = (event) => {
                    selected = index;
                    const startX = event.clientX;
                    const startY = event.clientY;
                    const oldX = item.x;
                    const oldY = item.y;

                    el.setPointerCapture(event.pointerId);

                    function move(e) {
                        item.x = Math.max(0, oldX + e.clientX - startX);
                        item.y = Math.max(0, oldY + e.clientY - startY);
                        el.style.left = item.x + "px";
                        el.style.top = item.y + "px";
                    }

                    function end() {
                        el.removeEventListener("pointermove", move);
                        el.removeEventListener("pointerup", end);
                    }

                    el.addEventListener("pointermove", move);
                    el.addEventListener("pointerup", end);
                };
            }

            stage.appendChild(el);
        });
    }

    function addItem(type) {
        if (!canEdit) return;

        items.push({
            type: type,
            name: type,
            x: 30 + (items.length % 4) * 135,
            y: 30 + Math.floor(items.length / 4) * 90
        });

        draw();
    }

    function deleteItem() {
        if (!canEdit || selected === null) return;

        items.splice(selected, 1);
        selected = null;
        draw();
    }

    async function saveItems() {
        if (!canEdit) return;

        const response = await fetch("/api/seating", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(items)
        });

        if (response.ok) {
            alert("Đã lưu sơ đồ lớp!");
        } else {
            alert("Không thể lưu sơ đồ.");
        }
    }

    draw();
    </script>
    """

    content = content.replace(
        "INITIAL_DATA",
        json.dumps(json.loads(initial_data))
    ).replace(
        "CAN_EDIT",
        "true" if can_edit else "false"
    )

    return render_page("Sơ đồ lớp", render_template_string(
        content,
        can_edit=can_edit
    ))


@app.route("/api/seating", methods=["POST"])
@login_required
@permission_required("seating")
def save_seating():
    items = request.get_json(silent=True)

    if not isinstance(items, list):
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400

    # Giới hạn kích thước dữ liệu để tránh lưu nội dung quá lớn
    if len(items) > 300:
        return jsonify({"error": "Sơ đồ có quá nhiều vật dụng"}), 400

    safe_items = []

    for item in items:
        if not isinstance(item, dict):
            continue

        safe_items.append({
            "type": str(item.get("type", ""))[:40],
            "name": str(item.get("name", ""))[:100],
            "x": max(0, min(int(item.get("x", 0)), 5000)),
            "y": max(0, min(int(item.get("y", 0)), 5000))
        })

    db = connect_db()
    db.execute("""
        INSERT INTO seating (id, data)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET data = excluded.data
    """, (json.dumps(safe_items, ensure_ascii=False),))
    db.commit()
    db.close()

    return jsonify({"success": True})


# ==========================================
# 12. QUẢN LÝ TÀI KHOẢN VÀ PHÂN QUYỀN
# ==========================================

@app.route("/accounts", methods=["GET", "POST"])
@login_required
def accounts():
    user = current_user()

    if user["role"] != "admin":
        return "Chỉ quản trị viên mới được quản lý tài khoản.", 403

    db = connect_db()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "teacher")

        if not username or len(password) < 8:
            flash("Tên tài khoản không được trống, mật khẩu cần ít nhất 8 ký tự.")
            db.close()
            return redirect(url_for("accounts"))

        if role not in ("teacher", "student"):
            role = "teacher"

        permissions = {
            key: bool(request.form.get(key))
            for key in PERMISSIONS
        }

        try:
            db.execute("""
                INSERT INTO users (username, password, role, permissions)
                VALUES (?, ?, ?, ?)
            """, (
                username,
                generate_password_hash(password),
                role,
                json.dumps(permissions)
            ))
            db.commit()
            flash("Đã tạo tài khoản.")
        except sqlite3.IntegrityError:
            flash("Tên tài khoản đã tồn tại.")

        db.close()
        return redirect(url_for("accounts"))

    rows = db.execute(
        "SELECT id, username, role, permissions FROM users ORDER BY id"
    ).fetchall()
    db.close()

    form = """
    <h3>Tạo tài khoản mới</h3>
    <form method="POST">
        <label>Tên đăng nhập</label>
        <input name="username" required>

        <label>Mật khẩu (ít nhất 8 ký tự)</label>
        <input name="password" type="password" minlength="8" required>

        <label>Loại tài khoản</label>
        <select name="role">
            <option value="teacher">Giáo viên</option>
            <option value="student">Học sinh</option>
        </select>

        <h3>Chọn quyền được chỉnh sửa</h3>
    """

    for key, label in PERMISSIONS.items():
        form += f"""
        <label style="display:block;margin:10px 0">
            <input type="checkbox" name="{key}" value="1"
                   style="width:auto">
            {label}
        </label>
        """

    form += """
        <button>Tạo tài khoản</button>
    </form>

    <hr>
    <h3>Tài khoản hiện có</h3>
    <table>
        <tr><th>Tên đăng nhập</th><th>Vai trò</th></tr>
    """

    for row in rows:
        form += f"""
        <tr>
            <td>{row['username']}</td>
            <td>{row['role']}</td>
        </tr>
        """

    form += "</table>"

    return render_page("Quản lý tài khoản", form)


# ==========================================
# 13. KHỞI ĐỘNG WEBSITE
# ==========================================

if __name__ == "__main__":
    init_db()

    print("================================")
    print("CLASS PORTAL đang khởi động...")
    print("Mở trình duyệt tại:")
    print("http://localhost:5000")
    print("Để thiết bị khác truy cập: http://IP-MAY-TINH:5000")
    print("================================")

    app.run(host="0.0.0.0", port=5000, debug=False)
