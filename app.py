from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import pymysql
import random
import os
import string
import re
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Akhil\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'


app = Flask(__name__)

app.secret_key = 'your-secret-key'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'admin@123'
app.config['MYSQL_DB'] = 'visidb'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def get_db_connection():
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        db=app.config['MYSQL_DB']
    )

def isLoggedIn():
    return 'name' in session

@app.route('/')
def index():
    status = isLoggedIn()
    # return redirect(url_for('cards'))
    return render_template('index.html', status=status)

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST':
        userName = request.form['name']
        email = request.form['email']
        password = request.form['password']
        random_number = ''.join(random.choices(string.digits, k=4))
        email_prefix = email[:3]
        userid = random_number + email_prefix.upper()
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users_table WHERE email = %s", (email,))
                user = cur.fetchone()
                if user:
                    message = 'Email already exists'
                    return render_template('register.html', message=message)
                else:
                    cur.execute("INSERT INTO users_table(userid, Name, email, password) VALUES(%s, %s, %s, %s)", 
                                (userid, userName, email, password))
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
                cur.execute("SELECT * FROM users_table WHERE email = %s AND password = %s", (email, password))
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
        name = session['name']
        return render_template('user.html', name=name, userid=session['userid'], status=True)
    else:
        return redirect(url_for('login'))

@app.route('/cards')
def cards():
    if not isLoggedIn():
        return redirect(url_for('login'))
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Use actual column names present in your database
                cur.execute("SELECT cardid, name, subname, email, phone,address, category FROM cards WHERE userid = %s", (session['userid'],))
                cards = cur.fetchall()
                return render_template('cards.html', cards=cards, status=True)
        finally:
            conn.close()




@app.route('/addcard', methods=['GET', 'POST'])
def addcard():
    if not isLoggedIn():
        return redirect(url_for('login'))
    else:
        phone_numbers = ['']
        email_addresses = ['']
        name = ''
        subname = ''
        address=''
        return render_template('add-card.html', status=True, phone_numbers=phone_numbers,address=address, email_addresses=email_addresses, name=name, subname=subname)

@app.route('/getdetails', methods=['POST'])
@app.route('/getdetails', methods=['POST'])
def getdetails():
    if 'photo' not in request.files:
        return redirect(request.url)
    photo = request.files['photo']
    if photo.filename == '':
        return redirect(request.url)
    if photo and allowed_file(photo.filename):
        filename = secure_filename(photo.filename)
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(photo_path)
        image_url = url_for('uploaded_file', filename=filename)

        # Extract data from image
        text, phone_numbers, email_addresses, name, subname, address = extract_text_from_image(photo_path)

        # Select first item from lists for form fields
        phone = phone_numbers[0] if phone_numbers else ''
        email = email_addresses[0] if email_addresses else ''
        address = address if isinstance(address, str) else ', '.join(address)

        return render_template(
            'add-card.html',
            image_url=image_url,
            text=text,
            phone=phone,
            email=email,
            name=name,
            subname=subname,
            address=address,
            status=True
        )
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

        print("======= OCR TEXT START =======")
        print(text)
        print("======= OCR TEXT END ========")

        # Split lines and clean them
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        print("\nLines extracted from image:")
        for i, line in enumerate(lines):
            print(f"{i+1}: {line}")

        # Extract phone numbers
        phone_numbers = re.findall(r'[\+\(]?[0-9][0-9.\-\(\) ]{8,}[0-9]', text)
        print("\nExtracted Phone Numbers:", phone_numbers)

        # Extract email addresses
        email_addresses = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
        print("Extracted Email Addresses:", email_addresses)

        # Extract names - typically the first two lines
        name = lines[0] if len(lines) > 0 else ''
        subname = lines[1] if len(lines) > 1 else ''
        print("Extracted Name:", name)
        print("Extracted Subname:", subname)

        # Extract address - avoid lines containing phone or email
        address_keywords = ['street', 'st.', 'road', 'rd.', 'block', 'lane', 'avenue', 'ave', 'sector', 'village', 'district', 'nagar', 'city', 'pin', 'state', 'zip', 'building', 'floor', 'no.', 'plot']
        address_lines = [
            line for line in lines
            if any(kw in line.lower() for kw in address_keywords)
            and not any(email in line for email in email_addresses)
            and not any(phone in line for phone in phone_numbers)
        ]
        
        # Fallback if nothing matched
        if not address_lines:
            address_lines = lines[2:]  # Skip first 2 lines (name/subname)

        address = ', '.join(address_lines)
        print("Extracted Address:", address)

        return text, phone_numbers, email_addresses, name, subname, address

    except Exception as e:
        print("Exception during image processing:", e)
        return str(e), [], [], '', '', ''

@app.route('/uploadcard', methods=['POST'])
def uploadcard():
    if request.method == 'POST':
        phone = request.form.get('phone')
        email = request.form.get('email')
        name = request.form.get('name')
        subname = request.form.get('subname')
        address=request.form.get('address')
        category = request.form.get('category')

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cards(name, subname, email, phone,address, category, userid) VALUES(%s, %s, %s,%s, %s, %s, %s)",
                    (name, subname, email, phone,address, category, session['userid'])
                )
                conn.commit()
                flash('Card saved successfully', 'success')
        except Exception as e:
            conn.rollback()
            print(f"An error occurred: {e}")
            flash('Failed to save card', 'danger')
        finally:
            conn.close()

    return redirect(url_for('cards'))
@app.route('/editcard/<int:card_id>', methods=['GET', 'POST'])
def edit_card(card_id):
    status = isLoggedIn()
    if not status:
        return redirect(url_for('login'))
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM cards WHERE cardid = %s AND userid = %s", (card_id, session['userid']))
                card = cur.fetchone()
                if card:
                    if request.method == 'POST':
                        name = request.form.get('name')
                        subname = request.form.get('subname')
                        email = request.form.get('email')
                        phone = request.form.get('phone')
                        address=request.form.get('address')
                        category = request.form.get('category')

                        cur.execute(
                            "UPDATE cards SET name = %s, subname = %s, email = %s, phone = %s,address= %s, category = %s WHERE cardid = %s AND userid = %s",
                            (name, subname, email, phone,address, category, card_id, session['userid'])
                        )
                        conn.commit()
                        flash('Card updated successfully', 'success')
                        return redirect(url_for('cards'))
                    else:
                        return render_template('edit-card.html', card=card, status=status)
                else:
                    flash('Card not found or you do not have permission to edit it', 'danger')
                    return redirect(url_for('cards'))
        finally:
            conn.close()
@app.route('/deletecard/<int:card_id>', methods=['POST'])
def delete_card(card_id):
    status = isLoggedIn()
    if not status:
        return redirect(url_for('login'))
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cards WHERE cardid = %s AND userid = %s", (int(card_id), session['userid']))
                conn.commit()
                flash('Card deleted successfully', 'success')
        except Exception as e:
            conn.rollback()
            print(f"An error occurred: {e}")
            flash('Failed to delete card', 'danger')
        finally:
            conn.close()
        return redirect(url_for('cards'))
@app.route('/logout')
def logout():
    session.pop('name', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)