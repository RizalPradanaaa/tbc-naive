from flask import Flask, request, render_template, flash, send_file, redirect, url_for, flash, session, jsonify
import mysql.connector
import pickle
import pandas as pd
from openpyxl import Workbook
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'

model = pickle.load(open('model.pkl', 'rb'))

# Koneksi database
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="naive-tbc"
)
db_cursor = db_connection.cursor(dictionary=True)

@app.route('/', methods=['GET', 'POST'])
def home():
    prediction = -1
    nama = None
    if request.method == 'POST':
        nama = request.form.get('nama')
        batuk = int(request.form.get('batuk'))
        demam = int(request.form.get('demam'))
        sesak_nafas = int(request.form.get('sesak_nafas'))
        berkeringat_malam = int(request.form.get('berkeringat_malam'))
        diabetes = int(request.form.get('diabetes'))
        perokok = int(request.form.get('perokok'))
        lansia = int(request.form.get('lansia'))


        input_features = pd.DataFrame([[batuk, demam, sesak_nafas, berkeringat_malam,
                                        diabetes, perokok, lansia]],
                                      columns=['batuk', 'demam', 'sesak_nafas',
                                               'berkeringat_malam', 'diabetes', 'perokok', 'lansia'])
        # print(input_features)
        prediction = model.predict(input_features)
        # print(prediction)
        prediction_value = int(prediction[0])

        # Insert data ke MySQL database
        # Insert data ke tabel predictions
        insert_predictions_query = """
            INSERT INTO dataset (name, batuk, demam, sesak_nafas, berkeringat_malam, diabetes, perokok, lansia, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        predictions_data = (nama, batuk, demam, sesak_nafas, berkeringat_malam, diabetes, perokok, lansia,  prediction_value)

        db_cursor.execute(insert_predictions_query, predictions_data)
        db_connection.commit()


    return render_template('index.html', prediction=prediction, nama=nama)



# admin
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    # Cek apakah email atau password kosong
    if not email or not password or not confirm_password:
        return jsonify({'message': 'Semua kolom harus diisi.', 'status': 'warning'}), 400

    # Cek apakah password dan konfirmasi password sama
    if password != confirm_password:
        return jsonify({'message': 'Password dan konfirmasi password tidak cocok.', 'status': 'warning'}), 400

    # Cek apakah email sudah terdaftar
    db_cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = db_cursor.fetchone()

    if user:
        return jsonify({'message': 'Email sudah terdaftar.', 'status': 'warning'}), 400

    # Hash password dan simpan ke database
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    db_cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_password))
    db_connection.commit()

    return jsonify({'message': 'Registrasi berhasil! Silakan login.', 'status': 'success'}), 201

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Pengecekan apakah sudah login
    if 'user_id' in session:
        flash('Anda sudah login.', 'info')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Cek apakah email atau password kosong
        if not email or not password:
            flash('Email dan password harus diisi.', 'warning')
            return redirect(url_for('login'))

        # Cek apakah user ada di database
        db_cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = db_cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login berhasil!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Login gagal. Periksa email dan password Anda.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Hapus sesi user_id
    session.pop('user_id', None)
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    # Pengecekan apakah sudah login
    if 'user_id' not in session:
        flash('Anda harus login terlebih dahulu.', 'danger')
        return redirect(url_for('login'))

    # Ambil nama pengguna yang sedang login
    db_cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
    user = db_cursor.fetchone()
    if user:
        nama_pengguna = user['email']  # Sesuaikan dengan kolom yang sesuai

        # Mengambil data dari tabel predictions dan users
        select_query = """
            SELECT * FROM dataset
        """
        db_cursor.execute(select_query)
        predictions = db_cursor.fetchall()

        total_predictions = len(predictions)
        total_negatif = sum(1 for prediction in predictions if prediction['status'] == 0)
        total_positif = sum(1 for prediction in predictions if prediction['status'] == 1)

        return render_template('admin.html', nama_pengguna=nama_pengguna, predictions=predictions,total_predictions=total_predictions,
                               total_negatif=total_negatif, total_positif=total_positif)
    else:
        flash('Data pengguna tidak ditemukan.', 'danger')
        return redirect(url_for('login'))

@app.route('/report', methods=['GET'])
def report():
    # Ambil semua data dari database
    select_query = """
            SELECT * FROM dataset
        """
    db_cursor.execute(select_query)
    data = db_cursor.fetchall()

    # Buat file Excel
    wb = Workbook()
    ws = wb.active
    ws.append(['Nama Lengkap', 'Batuk', 'Demam', 'Sesak Nafas', 'Berkeringat Malam', 'Diabetes', 'Perokok', 'Lansia', 'Status'])

    for row in data:
        # Sesuaikan dengan nama kolom yang benar dari tabel predictions
        ws.append([row['name'], row['batuk'], row['demam'], row['sesak_nafas'], row['berkeringat_malam'], row['diabetes'], row['perokok'], row['lansia'], row['status']])

    # Buat objek BytesIO untuk menulis file Excel
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='data_prediksi.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True)
