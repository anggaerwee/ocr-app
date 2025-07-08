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

        user.isactive = True
        db.commit()
        if not user:
            return jsonify({"msg": "Username tidak ditemukan"}), 401
        if not bcrypt.checkpw(password.encode('utf-8'), user.pswd.encode('utf-8')):
            return jsonify({"msg": "Password salah"}), 401
        
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

# @app.route('/api/filenames')
# def api_filenames():
#     session = Session()
#     try:
#         search = request.args.get('q', '').strip()
#         source = request.args.get('source', 'product')

#         table_name ='invoiceblur' if source == 'blur' else 'invoice'
#         base_query = f"""
#             SELECT DISTINCT filename, text
#             FROM {table_name}
#             WHERE filename IS NOT NULL AND filename != ''
#         """
#         if search:
#             base_query += " AND filename LIKE :search"
#             results = session.execute(
#                 text(base_query),
#                 {"search": f"%{search}%"}
#             ).fetchall()
#         else:
#             results = session.execute(text(base_query)).fetchall()
#         data = [{'id': row[0], 'text': row[0], 'fulltext': row[1]} for row in results]
#         return jsonify({'results': data})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#     finally:
#         session.close()

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

        results = session.execute(text(base_query), params).fetchall()

        data = [{'id': row[0], 'text': row[0], 'fulltext': row[1]} for row in results]
        return jsonify({'results': data})
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        session.close()

# @app.route('/api/products')
# @jwt_required()  # ← Penting agar bisa pakai get_jwt_identity()
# def api_products():
#     session = Session()
#     try:
#         user_id = get_jwt_identity()  # Sekarang bisa digunakan dengan aman
#         user = session.query(Msuser).filter(Msuser.userid == user_id).first()
#         if not user:
#             return jsonify({'error': 'User tidak ditemukan'}), 401

#         groupid = user.groupid
#         model = InvoiceBlur if request.args.get('source', 'product') == 'blur' else ProductTable

#         # ADMIN
#         if groupid == 1:
#             query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid)
#         else:
#             # USER BIASA - hanya lihat data miliknya
#             query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid).filter(model.useracid == user.userid)

#         # Filter tambahan
#         filename = request.args.get('filename', '').strip()
#         startdt = request.args.get('startdt', '').strip()
#         enddt = request.args.get('enddt', '').strip()
#         search_value = request.args.get("search[value]", "").strip()

#         if filename:
#             query = query.filter(model.filename == filename)
#         if startdt:
#             try:
#                 start_date = datetime.strptime(startdt, '%Y-%m-%d').date()
#                 query = query.filter(func.date(model.createddate) >= start_date)
#             except:
#                 pass
#         if enddt:
#             try:
#                 end_date = datetime.strptime(enddt, '%Y-%m-%d').date()
#                 query = query.filter(func.date(model.createddate) <= end_date)
#             except:
#                 pass

#         total_records = query.count()

#         if search_value:
#             query = query.filter(
#                 or_(
#                     model.product_number.ilike(f"%{search_value}%"),
#                     model.description.ilike(f"%{search_value}%"),
#                     model.filename.ilike(f"%{search_value}%"),
#                 )
#             )

#         filtered_records = query.count()
#         draw = int(request.args.get("draw", 1))
#         start = int(request.args.get("start", 0))
#         length = int(request.args.get("length", 10))
#         results = query.offset(start).limit(length).all()

#         data = []
#         for item, usernm in results:
#             row = {
#                 'id': item.id,
#                 'product_number': item.product_number,
#                 'description': item.description,
#                 'quantity': item.quantity,
#                 'unit_price': item.unit_price,
#                 'discount': item.discount,
#                 'line_total': item.line_total,
#                 'text': item.text,
#                 'filename': item.filename,
#                 'createddate': item.createddate.strftime('%d-%m-%Y %H:%M:%S') if item.createddate else None,
#             }
#             if groupid == 1:
#                 row['usernm'] = usernm
#             data.append(row)

#         return jsonify({
#             'draw': draw,
#             'recordsTotal': total_records,
#             'recordsFiltered': filtered_records,
#             'data': data
#         })

#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#     finally:
#         session.close()

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

        # Admin: semua data
        if groupid == 1:
            query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid)
        else:
            # User biasa: hanya data sendiri
            query = session.query(model, Msuser.usernm).join(Msuser, Msuser.userid == model.useracid)\
                .filter(model.useracid == user.userid)

        # Filter tambahan
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

# CHUNK_DIR = 'temp_chunks'
# @app.route('/submit', methods=['POST'])
# def submit_file():
#     try:
#         uuid = request.form.get('dzuuid')
#         index = int(request.form.get('dzchunkindex', 0))
#         total_chunks = int(request.form.get('dztotalchunkcount', 1))
#         filename = request.form.get('filename')
#         file = request.files.get('file')

#         if not all([uuid, filename, file]):
#             return jsonify({'error': 'Missing required data'}), 400

#         chunk_path = os.path.join(CHUNK_DIR, f"{uuid}_{index}")
#         file.save(chunk_path)

#         if index + 1 == total_chunks:
#             combined = b''
#             for i in range(total_chunks):
#                 chunk_file = os.path.join(CHUNK_DIR, f"{uuid}_{i}")
#                 if not os.path.exists(chunk_file):
#                     return jsonify({'error': f'Chunk {i} missing'}), 400
#                 with open(chunk_file, 'rb') as f:
#                     combined += f.read()
#                 os.remove(chunk_file)

#             final_stream = BytesIO(combined)
#             final_stream.seek(0)

#             output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#             with open(output_path, 'wb') as f:
#                 f.write(final_stream.getbuffer())

#             full_text = ""
#             ocr_wer = None
#             if filename.lower().endswith('.pdf'):
#                 images = convert_from_bytes(final_stream.read(), dpi=205)
#                 full_text = ""
#                 original_all = ""
#                 enhanced_all = ""

#                 for idx, img in enumerate(images, start=1):
#                     gray = img.convert("L")
#                     binarized = gray.point(lambda p: 255 if p > 128 else 0)

#                     original_text = pytesseract.image_to_string(gray, config='--oem 3 --psm 6', lang='eng+ind')
#                     enhanced_text = pytesseract.image_to_string(binarized, config='--oem 3 --psm 6', lang='eng+ind')

#                     original_all += original_text + "\n"
#                     enhanced_all += enhanced_text + "\n"

#                     full_text += f"\n\n--- Halaman {idx} ---\n{enhanced_text}"

#                 ocr_wer = wer(original_all.strip(), enhanced_all.strip())

#             elif filename.lower().endswith('.webp'):
#                 temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#                 text, ocr_wer, line_wer_result = extract_image_with_ocr(temp_path)
#                 full_text = text
#             else:
#                 return jsonify({'error': 'Format file tidak didukung'}), 400

#             flash((f"{filename} berhasil diupload. Klik Save untuk proses ke database.", filename), 'success')
#             return jsonify({'text': full_text, 'wer': ocr_wer, 'wer_per_line': line_wer_result})

#         return '', 200

#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

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
                images = convert_from_bytes(final_stream.read(), dpi=205)
                for idx, img in enumerate(images, start=1):
                    text = pytesseract.image_to_string(img, config='--oem 3 --psm 6', lang='eng+ind')
                    full_text += f"\n\n--- Halaman {idx} ---\n{text}"
            elif filename.lower().endswith('.webp'):
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                with open(temp_path, 'wb') as f:
                    f.write(final_stream.read())
                text, ocr_wer = extract_image_with_ocr(temp_path)
                full_text = text
            else:
                return jsonify({'error': 'Format file tidak didukung'}), 400

            flash((f"{filename} berhasil diupload. Klik Save untuk proses ke database.", filename), 'success')
            return jsonify({'text': full_text, 'wer':ocr_wer})

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
        user_id = get_jwt_identity()
        csv_filename = process_file(full_path, mode=mode, text_override=text_override, useracid=user_id)

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

        # ADMIN: Hitung semua data
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
    app.run(host='0.0.0.0', debug=True, port=5000)