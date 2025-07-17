from flask import Flask, render_template, request, redirect, flash, send_from_directory, jsonify, url_for, send_file, make_response
from function import process_file, ProductTable, InvoiceBlur, Msuser, Session, write_csv_with_delimiter, extract_text_with_ocr, extract_image_with_ocr
import bcrypt, os, base64
from os import listdir
import csv
from sqlalchemy.sql import text,func, or_
from io import StringIO, BytesIO
from flask import Response
from datetime import datetime
from sqlalchemy.orm import sessionmaker
import pytesseract
from PIL import Image
from jiwer import wer
from pdf2image import convert_from_bytes
from datetime import timedelta
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, get_jwt_identity, verify_jwt_in_request, set_access_cookies, unset_jwt_cookies
)
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from pdf2image import convert_from_path
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['JWT_SECRET_KEY'] = 'very-secret-key-12345'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ERROR_MESSAGE_KEY'] = None
app.secret_key = 'supersecretkey'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)
CORS(app, supports_credentials=True)

@jwt.unauthorized_loader
def custom_unauthorized_response(err_str):
    return redirect('/')

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return redirect('/')

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return redirect('/')

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return redirect('/')

@jwt.needs_fresh_token_loader
def needs_fresh_token_callback(jwt_header, jwt_payload):
    return redirect('/')

@app.before_request
def restrict_routes():
    allowed_paths = ['/', '/api/login', '/static']

    if any(request.path.startswith(path) for path in allowed_paths):
        return

    try:
        verify_jwt_in_request()
        user = get_jwt_identity()
        if not user:
            return redirect('/')
    except:
        return redirect('/')

    if user and request.path in ['/', '/api/login']:
        return redirect('/dashboard')

@app.context_processor
def inject_user():
    try:
        verify_jwt_in_request()
        user = get_jwt_identity()
    except:
        user = None
    return dict(user=user)
    
@app.route('/')
def login_page():
    try:
        verify_jwt_in_request()
        user = get_jwt_identity()
        if user:
            return redirect('/dashboard')
    except:
        pass
    response = make_response(render_template('components/content.html', view='auth', title='OcrConvert', subtitle='Sign In'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Ecpires'] = '0'
    return response

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    db = Session()
    try:
        user = db.query(Msuser).filter(Msuser.usernm == username).first()

        if not user:
            return jsonify({"msg": "Username tidak ditemukan"}), 401
        if not bcrypt.checkpw(password.encode('utf-8'), user.pswd.encode('utf-8')):
            return jsonify({"msg": "Password salah"}), 401
        
        user.isactive = True
        db.commit()
        token = create_access_token(identity=str(user.userid))
        response = jsonify({"msg": "Login berhasil", "token": token})
        set_access_cookies(response, token)
        return response, 200

    finally:
        db.close()

@app.route('/logout')
@jwt_required()  
def logout():
    db = Session()
    try:
        user_id = get_jwt_identity() 
        user = db.query(Msuser).filter_by(userid=int(user_id)).first()

        if user:
            user.isactive = False
            db.commit()
    except Exception as e:
        print("Logout error:", e)
        db.rollback()
    finally:
        db.close()

    response = make_response(redirect('/'))
    unset_jwt_cookies(response)
    return response

@app.route('/dashboard')
@jwt_required()
def utem():
    db = Session()
    try:
        user_id = get_jwt_identity()
        user = db.query(Msuser).filter(Msuser.userid == user_id).first()
        return render_template(
            'components/content.html',
            title='OcrConvert',
            subtitle='Home',
            view='dashboard',
            user=user
        )
    finally:
        db.close()


@app.route('/convert')
def home():
    try:
        verify_jwt_in_request()
        user = get_jwt_identity()
        folder = app.config['UPLOAD_FOLDER']
        files = [f for f in listdir(folder) if f.endswith('.csv')] if os.path.exists(folder) else []
        response = make_response(render_template('components/content.html', files=files, view='index', title='OcrConvert', subtitle='Upload'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        flash(('error', 'Anda harus login terlebih dahulu.'))
        return redirect('/')
@app.route('/data')
@jwt_required()
def data():
    return render_template('components/content.html', view='data', title='OcrConvert', subtitle='Data')

@app.route('/api/filenames')
@jwt_required()
def api_filenames():
    session = Session()
    try:
        user_id = get_jwt_identity()
        user = session.query(Msuser).filter(Msuser.userid == user_id).first()
        if not user:
            return jsonify({'error': 'User tidak ditemukan'}), 401

        search = request.args.get('q', '').strip()
        source = request.args.get('source', 'product')
        table_name = 'invoiceblur' if source == 'blur' else 'invoice'

        base_query = f"SELECT DISTINCT filename, text FROM {table_name} WHERE filename IS NOT NULL AND filename != ''"

        params = {}
        if search:
            base_query += " AND filename LIKE :search"
            params['search'] = f"%{search}%"

        if user.groupid != 1:
            base_query += " AND useracid = :user_id"
            params['user_id'] = user.userid

        results = session.execute(text(base_query), params).fetchall()

        data = [{'id': row[0], 'text': row[0], 'fulltext': row[1]} for row in results]
        return jsonify({'results': data})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        session.close()

@app.route('/api/products')
@jwt_required()
def api_products():
    session = Session()
    try:
        user_id = get_jwt_identity()
        user = session.query(Msuser).filter(Msuser.userid == user_id).first()
        if not user:
            return jsonify({'error': 'User tidak ditemukan'}), 401

        groupid = user.groupid
        source = request.args.get('source', 'product')
        model = InvoiceBlur if source == 'blur' else ProductTable

        if groupid == 1:
            query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid)
        else:
            query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid)\
                .filter(model.useracid == user.userid)

        filename = request.args.get('filename', '').strip()
        startdt = request.args.get('startdt', '').strip()
        enddt = request.args.get('enddt', '').strip()
        search_value = request.args.get("search[value]", "").strip()

        if filename:
            query = query.filter(model.filename == filename)

        if startdt:
            try:
                start_date = datetime.strptime(startdt, '%Y-%m-%d').date()
                query = query.filter(func.date(model.createddate) >= start_date)
            except ValueError:
                pass

        if enddt:
            try:
                end_date = datetime.strptime(enddt, '%Y-%m-%d').date()
                query = query.filter(func.date(model.createddate) <= end_date)
            except ValueError:
                pass

        total_records = query.count()

        if search_value:
            query = query.filter(
                or_(
                    model.product_number.ilike(f"%{search_value}%"),
                    model.description.ilike(f"%{search_value}%"),
                    model.filename.ilike(f"%{search_value}%")
                )
            )

        filtered_records = query.count()
        draw = int(request.args.get("draw", 1))
        start = int(request.args.get("start", 0))
        length = int(request.args.get("length", 10))
        results = query.offset(start).limit(length).all()

        data = []
        for item, usernm in results:
            data.append({
                'id': item.id,
                'product_number': item.product_number,
                'description': item.description,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'discount': item.discount,
                'line_total': item.line_total,
                'text': item.text,
                'filename': item.filename,
                'createddate': item.createddate.strftime('%d-%m-%Y %H:%M:%S') if item.createddate else None,
                'usernm': usernm
            })

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

CHUNK_DIR = 'temp_chunks'
@app.route('/submit', methods=['POST'])
def submit_file():
    try:
        uuid = request.form.get('dzuuid')
        index = int(request.form.get('dzchunkindex', 0))
        total_chunks = int(request.form.get('dztotalchunkcount', 1))
        filename = request.form.get('filename')
        file = request.files.get('file')

        if not all([uuid, filename, file]):
            return jsonify({'error': 'Missing required data'}), 400

        chunk_path = os.path.join(CHUNK_DIR, f"{uuid}_{index}")
        file.save(chunk_path)

        if index + 1 == total_chunks:
            combined = b''
            for i in range(total_chunks):
                chunk_file = os.path.join(CHUNK_DIR, f"{uuid}_{i}")
                if not os.path.exists(chunk_file):
                    return jsonify({'error': f'Chunk {i} missing'}), 400
                with open(chunk_file, 'rb') as f:
                    combined += f.read()
                os.remove(chunk_file)

            final_stream = BytesIO(combined)
            final_stream.seek(0)

            output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(output_path, 'wb') as f:
                f.write(final_stream.getbuffer())

            full_text = ""
            ocr_wer = ""

            if filename.lower().endswith('.pdf'):
                pages = convert_from_path(output_path, dpi=500)
                total_pages = len(pages)

                wer_list = []
                full_text_parts = []

                for image in pages:
                    # text, page_wer = extract_text_with_ocr(image)
                    text, page_wer, wer_line = extract_text_with_ocr(image)
                    if text is None:
                        text = ""
                        page_wer = 1.0
                    full_text_parts.append(text)
                    wer_list.append(page_wer)

                full_text = "\n".join(full_text_parts)
                ocr_wer = sum(wer_list) / len(wer_list) if wer_list else 1.0

            elif filename.lower().endswith('.webp'):
                text, ocr_wer, wer_line = extract_image_with_ocr(output_path)
                full_text = text

            else:
                return jsonify({'error': 'Format file tidak didukung'}), 400

            flash((f"{filename} berhasil diupload. Klik Save untuk proses ke database.", filename), 'success')
            return jsonify({'text': full_text, 'wer': ocr_wer, 'wer_per_line':wer_line})

        return '', 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/save/<path:filepath>', methods=['POST'])
@jwt_required()
def save(filepath):
    try:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
        if not os.path.exists(full_path):
            return jsonify({'status': 'error', 'message': f"File {filepath} tidak ditemukan."}), 404

        mode = request.form.get('mode', 'product').lower()
        text_override = request.form.get('text') if mode == "blur" else None
        wer_per_line_raw = request.form.get("wer_per_line")
        user_id = get_jwt_identity()

        wer_per_line = None
        if wer_per_line_raw:
            try:
                wer_per_line = json.loads(wer_per_line_raw)
            except Exception as e:
                return jsonify({'status': 'error', 'message': f"WER data invalid: {str(e)}"}), 400

        csv_filename = process_file(
            full_path,
            mode=mode,
            text_override=text_override,
            useracid=user_id,
            wer_per_line=wer_per_line
        )

        if csv_filename == "error_blur":
            return jsonify({
                'status': 'error_blur',
                'message': "Data terlalu buram atau gagal diproses. Simpan ke tabel blur?"
            })
        elif csv_filename:
            return jsonify({
                'status': 'success',
                'message': f"File {filepath} berhasil diproses.",
                'csv': csv_filename
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"File {filepath} gagal diproses."
            }), 500

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

    current_datetime = datetime.now().strftime("%d-%m-%Y")
    download_name = f"{os.path.splitext(filename)[0]}-{current_datetime}.csv"

    return send_file(
        file_path,
        as_attachment=True,
        mimetype='text/csv',
        download_name=download_name
    )

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
        current_date = datetime.now().strftime("%d-%m-%Y")
        if source == 'blur':
            filenamen = f"all_products-blur-{current_date}.csv"
        else:
            filenamen = f"all_products-{current_date}.csv"

        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={filenamen}'}
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
    
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route("/api/invoice_count")
@jwt_required()
def invoice_count():
    session = Session()
    try:
        source = request.args.get('source', 'product')
        user_id = get_jwt_identity()
        user = session.query(Msuser).filter_by(userid=user_id).first()

        if not user:
            return jsonify({'error': 'User tidak ditemukan'}), 401

        model = InvoiceBlur if source == 'blur' else ProductTable

        if user.groupid == 1:
            count = session.query(model).count()
        else:
            count = session.query(model).filter_by(useracid=user.userid).count()

        return jsonify({"count": count})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', debug=True, port=port)