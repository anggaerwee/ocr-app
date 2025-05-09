from flask import Flask, render_template, request, redirect, flash
from function import extract_table_from_pdf
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'sample'
app.secret_key = 'supersecretkey'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def process_file():  

    try:
        file = request.files['file']
        if file.filename == '':
            flash('Form tidak boleh kosong', 'error')
            return redirect('/')

        if not file.filename.endswith('.pdf') or file.filename.endswith('.webp'):
            flash(f"{file.filename} Harus berformat pdf & webp ")
            return redirect('/')
        
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            try:
                extract_table_from_pdf(filepath)
                flash(f"{file.filename} Berhasil disimpan di database", 'success')
            except Exception as e:
                flash(f"File {file.filename} gagal disimpan di database : {e}")

            return redirect('/')
    except Exception as e:
        flash(f"terjadi kesalahan : {e}")
        return redirect('/')
    
if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
