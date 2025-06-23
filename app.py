from flask import Flask, render_template, request, redirect, flash, send_from_directory, jsonify, url_for
from function import process_file, ProductTable, InvoiceBlur, Session, write_csv_with_delimiter, extract_text_with_ocr, extract_image_with_ocr
import os
import csv
from sqlalchemy.sql import text
from io import StringIO
from flask import Response
import pytesseract
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
        source = request.args.get('source', 'product')

        table_name ='invoiceblur' if source == 'blur' else 'invoice'
        base_query = f"""
            SELECT DISTINCT filename, text
            FROM {table_name}
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
    source = request.args.get('source', 'product')
    if source == 'blur':
        products = InvoiceBlur.get_all(Session())
    else:
        products = ProductTable.get_all(Session())
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
        full_text = ""

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
                from pdf2image import convert_from_path
                images = convert_from_path(filepath, dpi=500)
                for page_num, image in enumerate(images, start=1):
                    custom_config = r'--oem 3 --psm 6'
                    page_text = pytesseract.image_to_string(image, config=custom_config, lang='eng+ind')
                    full_text += f"\n\n--- Halaman {page_num} ---\n{page_text}"
            elif file.filename.endswith('.webp'):
                text = extract_image_with_ocr(filepath)
                full_text += text

            flash((f"{file.filename} berhasil diupload. Klik Save untuk proses ke database.", file.filename), 'success')

        return jsonify({'text': full_text})
    except Exception as e:
        flash((f"Terjadi kesalahan : {e}", ''), 'error')
        return '', 500

    
@app.route('/save/<path:filepath>', methods=['POST'])
def save(filepath):
    try:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
        if not os.path.exists(full_path):
            return jsonify({'status': 'error', 'message': f"File {filepath} tidak ditemukan."}), 404
        mode = request.form.get('mode', 'product') 
        csv_filename = process_file(full_path, mode=mode)
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
    session = Session()
    source = request.args.get('source', 'product')

    try:
        if source == 'blur':
            products = InvoiceBlur.get_all(session)
        else:
            products = ProductTable.get_all(session)

        if not products:
            return "Tidak Ada Data Untuk Diunduh", 404

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
    finally:
        session.close()

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    source = request.args.get('source', 'product')
    if source == 'blur':
        result = InvoiceBlur.delete(id)
    else:
        result = ProductTable.delete(id)
    if result:
        return jsonify({"message": "Deleted"}), 200
    else:
        return jsonify({"error": "Not found"}), 404

@app.route('/deleteall')
def delete_all():
    source = request.args.get('source', 'product')
    try:
        session = Session()
        if source == 'blur':
            session.query(InvoiceBlur).delete()
        else:
            session.query(ProductTable).delete()
        session.commit()
        session.close()
        return redirect(url_for('data'))
    except Exception as e:
        return f"Error: {e}"
    
@app.route("/api/invoice_count")
def invoice_count():
    source = request.args.get('source', 'product')
    if source == 'blur':
        count = len(InvoiceBlur.get_all(Session()))
    else:
        count = len(ProductTable.get_all(Session()))
    return jsonify({"count": count})


if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=True)