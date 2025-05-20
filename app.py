from flask import Flask, render_template, request, redirect, flash, send_from_directory, jsonify
from function import process_file
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'output'
app.secret_key = 'supersecretkey'

@app.route('/')
def home():
    files = []
    folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(folder):
        files = [f for f in os.listdir(folder) if f.endswith('.csv')]
    return render_template('index.html', files=files)

@app.route('/submit', methods=['POST'])
def submit_file():
    try:
        # Untuk multi-file
        files = request.files.getlist('file')
        for file in files:
            if file.filename == '':
                flash(('Form tidak boleh kosong', ''), 'error')
                continue

            if not (file.filename.endswith('.pdf') or file.filename.endswith('.webp')):
                flash((f"{file.filename} harus berformat pdf atau webp", ''), 'error')
                continue

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            csv_filename = process_file(filepath)
            if csv_filename:
                flash((f"{file.filename} Berhasil disimpan di database", csv_filename), 'success')
            else:
                flash((f"File {file.filename} gagal disimpan di database", ''), 'error')
        return '', 204  # Untuk Dropzone, tidak perlu redirect
    except Exception as e:
        flash((f"terjadi kesalahan : {e}", ''), 'error')
        return '', 500

@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    folder = app.config['UPLOAD_FOLDER']
    return send_from_directory(folder, filename, as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)