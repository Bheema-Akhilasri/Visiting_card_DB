from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import random
import os
import string
import re
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
import oracledb
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Akhil\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = 'your-secret-key'
dsn = "localhost:1521/orclpdb"
app.config['ORACLE_HOST'] = 'localhost'
app.config['ORACLE_PORT'] = '1521'
app.config['ORACLE_SERVICE'] = 'orclpdb'
app.config['ORACLE_USER'] = 'admin1'
app.config['ORACLE_PASSWORD'] = 'admin1'


port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=True)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def get_db_connection():
    dsn = f"{app.config['ORACLE_HOST']}:{app.config['ORACLE_PORT']}/{app.config['ORACLE_SERVICE']}"
    return oracledb.connect(
        user=app.config['ORACLE_USER'],
        password=app.config['ORACLE_PASSWORD'],
        dsn=dsn
    )

def isLoggedIn():
    return 'name' in session

@app.route('/')
def index():
    return render_template('index.html', status=isLoggedIn())

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST':
        userName = request.form['name']
        email = request.form['email']
        password = request.form['password']
        userid = ''.join(random.choices(string.digits, k=4)) + email[:3].upper()

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users_table WHERE email = :email", {'email': email})
                user = cur.fetchone()
                if user:
                    message = 'Email already exists'
                else:
                    cur.execute("INSERT INTO users_table(userid, name, email, password) VALUES(:userid, :name, :email, :password)",
                                {'userid': userid, 'name': userName, 'email': email, 'password': password})
                    conn.commit()
                    message = 'User created successfully'
        finally:
            conn.close()
    return render_template('register.html', message=message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users_table WHERE email = :email AND password = :password",
                            {'email': email, 'password': password})
                user = cur.fetchone()
                if user:
                    session['name'] = user[1]
                    session['userid'] = user[0]
                    return redirect(url_for('dashboard'))
                else:
                    message = 'Invalid email or password'
        finally:
            conn.close()
    return render_template('login.html', message=message)

@app.route('/dashboard')
def dashboard():
    if isLoggedIn():
        return render_template('user.html', name=session['name'], userid=session['userid'], status=True)
    return redirect(url_for('login'))

@app.route('/cards')
def cards():
    if not isLoggedIn():
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cardid, name, subname, email, phone, address, category FROM cards WHERE userid = :userid",
                        {'userid': session['userid']})
            cards = cur.fetchall()
        return render_template('cards.html', cards=cards, status=True)
    finally:
        conn.close()

@app.route('/addcard', methods=['GET', 'POST'])
def addcard():
    if not isLoggedIn():
        return redirect(url_for('login'))
    return render_template('add-card.html', status=True, phone_numbers=[''], email_addresses=[''], name='', subname='', address='')

@app.route('/getdetails', methods=['POST'])
def getdetails():
    if 'photo' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)

    photo = request.files['photo']

    if photo.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)

    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)

        # Ensure uploads folder exists
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        # Save file
        photo_path = os.path.join(upload_folder, filename)
        try:
            photo.save(photo_path)
        except Exception as e:
            flash(f'File save failed: {str(e)}', 'danger')
            return redirect(request.url)

        image_url = url_for('uploaded_file', filename=filename)

        # Extract text
        text, phone_numbers, email_addresses, name, subname, address = extract_text_from_image(photo_path)

        return render_template(
            'add-card.html',
            image_url=image_url,
            text=text,
            phone=phone_numbers[0] if phone_numbers else '',
            email=email_addresses[0] if email_addresses else '',
            name=name,
            subname=subname,
            address=address,
            status=True
        )

    flash('Unsupported file type', 'danger')
    return redirect(request.url)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        phone_numbers = re.findall(r'[\+\(]?[0-9][0-9.\-\(\) ]{8,}[0-9]', text)
        email_addresses = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)

        name = lines[0] if len(lines) > 0 else ''
        subname = lines[1] if len(lines) > 1 else ''

        address_keywords = ['street', 'st.', 'road', 'rd.', 'block', 'lane', 'avenue', 'ave', 'sector', 'village', 'district', 'nagar', 'city', 'pin', 'state', 'zip', 'building', 'floor', 'no.', 'plot']
        address_lines = [line for line in lines[2:] if any(kw in line.lower() for kw in address_keywords)]
        address = ', '.join(address_lines)
        print(f"Extracted Lines:\n{lines}") 

        return text, phone_numbers, email_addresses, name, subname, address
    except Exception as e:
        return str(e), [], [], '', '', ''

@app.route('/uploadcard', methods=['POST'])
def uploadcard():
    if request.method == 'POST':
        phone = request.form.get('phone')
        email = request.form.get('email')
        name = request.form.get('name')
        subname = request.form.get('subname')
        address = request.form.get('address')
        category = request.form.get('category')

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cards(name, subname, email, phone, address, category, userid)
                    VALUES(:name, :subname, :email, :phone, :address, :category, :userid)
                """,
                {
                    'name': name,
                    'subname': subname,
                    'email': email,
                    'phone': phone,
                    'address': address,
                    'category': category,
                    'userid': session['userid']
                })
                conn.commit()
                flash('Card saved successfully', 'success')
        except Exception as e:
            conn.rollback()
            flash('Failed to save card', 'danger')
        finally:
            conn.close()
    return redirect(url_for('cards'))

@app.route('/editcard/<int:card_id>', methods=['GET', 'POST'])
def edit_card(card_id):
    if not isLoggedIn():
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cards WHERE cardid = :cardid AND userid = :userid",
                        {'cardid': card_id, 'userid': session['userid']})
            card = cur.fetchone()
            if card:
                if request.method == 'POST':
                    updated_data = {
                        'name': request.form.get('name'),
                        'subname': request.form.get('subname'),
                        'email': request.form.get('email'),
                        'phone': request.form.get('phone'),
                        'address': request.form.get('address'),
                        'category': request.form.get('category'),
                        'cardid': card_id,
                        'userid': session['userid']
                    }
                    cur.execute("""
                        UPDATE cards SET
                            name = :name,
                            subname = :subname,
                            email = :email,
                            phone = :phone,
                            address = :address,
                            category = :category
                        WHERE cardid = :cardid AND userid = :userid
                    """, updated_data)
                    conn.commit()
                    flash('Card updated successfully', 'success')
                    return redirect(url_for('cards'))
                return render_template('edit-card.html', card=card, status=True)
            flash('Card not found or you do not have permission to edit it', 'danger')
    finally:
        conn.close()
    return redirect(url_for('cards'))

@app.route('/deletecard/<int:card_id>', methods=['POST'])
def delete_card(card_id):
    if not isLoggedIn():
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cards WHERE cardid = :cardid AND userid = :userid",
                        {'cardid': card_id, 'userid': session['userid']})
            conn.commit()
            flash('Card deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash('Failed to delete card', 'danger')
    finally:
        conn.close()
    return redirect(url_for('cards'))

@app.route('/logout')
def logout():
    session.pop('name', None)
    session.pop('userid', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
