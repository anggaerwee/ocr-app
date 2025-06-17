from flask import Flask, render_template, request, redirect, flash, send_from_directory, jsonify, url_for
from function import process_file, ProductTable, Session, write_csv_with_delimiter, extract_text_with_ocr, extract_image_with_ocr
import os
import csv
from sqlalchemy.sql import text
from io import StringIO
from flask import Response
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'output'
app.secret_key = 'supersecretkey'

@app.route('/')
def home():
    files = []
    folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(folder):
        files = [f for f in os.listdir(folder) if f.endswith('.csv')]
    return render_template('index.html', files=files, title='OcrConvert')

@app.route('/data')
def data():
    return render_template('data.html', title='OcrConvert')

@app.route('/api/filenames')
def api_filenames():
    session = Session()
    try:
        search = request.args.get('q', '').strip()
        base_query = """
            SELECT DISTINCT filename, text
            FROM tb_product
            WHERE filename IS NOT NULL AND filename != ''
        """
        if search:
            base_query += " AND filename LIKE :search"
            results = session.execute(
                text(base_query),
                {"search": f"%{search}%"}
            ).fetchall()
        else:
            results = session.execute(text(base_query)).fetchall()
        data = [{'id': row[0], 'text': row[0], 'fulltext': row[1]} for row in results]
        return jsonify({'results': data})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        session.close()

        
@app.route('/api/products')
def api_products():
    products = ProductTable.get_all()
    data = [
        {
            'id' : p.id,
            'product_number': p.product_number,
            'description': p.description,
            'quantity': p.quantity,
            'unit_price': p.unit_price,
            'discount': p.discount,
            'line_total': p.line_total,
            'text': p.text,
            'filename': p.filename,
            'createddate': p.createddate.strftime('%d-%m-%Y %H:%M:%S') if p.createddate else None
        }
        for p in products
    ]
    print("[DEBUG] Data to return as JSON:")
    for item in data:
        print(item)
    return jsonify({'data': data})


@app.route('/submit', methods=['POST'])
def submit_file():
    try:
        files = request.files.getlist('file')
        text = ""
        for file in files:
            if file.filename == '':
                flash(('Form tidak boleh kosong', ''), 'error')
                continue

            if not (file.filename.endswith('.pdf') or file.filename.endswith('.webp')):
                flash((f"{file.filename} harus berformat pdf atau webp", ''), 'error')
                continue

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            if file.filename.endswith('.pdf'):
                text = extract_text_with_ocr(filepath, 1)
            elif file.filename.endswith('.webp'):
                text = extract_image_with_ocr(filepath)
            else:
                text = ""

            flash((f"{file.filename} berhasil diupload. Klik Save untuk proses ke database.", file.filename), 'success')
        return jsonify({'text': text})
    except Exception as e:
        flash((f"terjadi kesalahan : {e}", ''), 'error')
        return '', 500
    
@app.route('/save/<path:filepath>', methods=['POST'])
def save(filepath):
    try:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
        if not os.path.exists(full_path):
            return jsonify({'status': 'error', 'message': f"File {filepath} tidak ditemukan."}), 404

        csv_filename = process_file(full_path)
        if csv_filename:
            return jsonify({'status': 'success', 'message': f"{filepath} berhasil diproses dan disimpan ke database.", 'csv': csv_filename})
        else:
            return jsonify({'status': 'error', 'message': f"File {filepath} gagal diproses."}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    folder = app.config['UPLOAD_FOLDER']
    if not filename.lower().endswith('.csv'):
        filename = os.path.splitext(filename)[0] + '.csv'
    file_path = os.path.join(folder, filename)  
    if not os.path.exists(file_path):
        flash(('error', f'File {filename} tidak ditemukan.'))
        return redirect('/')
    return send_from_directory(folder, filename, as_attachment=True, mimetype='text/csv')

@app.route('/downloadall', methods=['GET'])
def download_all():
    products = ProductTable.get_all()
    if not products:
        flash(('Tidak ada data yang diunduh', ''), 'error')
        return redirect(url_for('home'))
    
    si = StringIO()
    writer = csv.writer(si, delimiter=';')
    writer.writerow(['product_number', 'description', 'quantity', 'unit_price', 'discount', 'line_total'])
    for p in products:
        writer.writerow([
            p.product_number,
            p.description,
            f"{p.quantity:.2f}" if isinstance(p.quantity, (int, float)) else p.quantity,
            f"{p.unit_price:.2f}" if isinstance(p.unit_price, (int, float)) else p.unit_price,
            f"{p.discount:.2f}%" if isinstance(p.discount, (int, float)) else p.discount,
            f"{p.line_total:.2f}" if isinstance(p.line_total, (int, float)) else p.line_total
        ])
    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=all_products.csv'}
    )
@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    result = ProductTable.delete(id)
    if result:
        return jsonify({"message": "Deleted"}), 200
    else:
        return jsonify({"error": "Not found"}), 404

@app.route('/deleteall')
def delete_all():
    try:
        session = Session()
        session.query(ProductTable).delete()
        session.commit()
        session.close()
        return redirect(url_for('data'))
    except Exception as e:
        return f"Error: {e}"
    
@app.route("/api/invoice_count")
def invoice_count():
    count = len(ProductTable.get_all())
    return jsonify({"count": count})


if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=True)