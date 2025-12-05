import requests
import os
import io
import csv
import re
import zipfile
import sys
from pydub import AudioSegment


# 1. KONFIGURASI PROYEK 

# URL CSV yang berisi daftar lagu dan tautan media.
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQqfRG03F7ovegIK6aiNGEZbaArjZeq3DeEjJO8sZH5qnTB4ENlt8VX44Usa2C-Ci8k0utFYfITI8YV/pub?output=csv"

# Nama direktori tempat file MP3 akan diunduh dan diproses.
DOWNLOAD_DIR = "Kidung_Reformed_Injili_MP3"

# Nama file output.
ZIP_FILENAME = "Kidung_Reformed_Injili_Semua_Lagu.zip"
GABUNGAN_FILENAME = "Kidung_Reformed_Injili_FULL_ALBUM.mp3"


# 2. FUNGSI UTILITY ---

def clean_filename(text):
    """Membersihkan teks untuk digunakan sebagai nama file yang aman."""
    # Menghapus karakter yang tidak aman untuk nama file.
    return re.sub(r'[\/:*?"<>|.]', '', text).replace(' ', '_').replace(',', '')


def download_mp3_and_get_list():
    """
    Mengambil data lagu dari CSV Google Sheets, mendownload file MP3 yang belum
    ada, dan mengembalikan daftar path file lokal dari semua MP3 yang berhasil.

    Returns:
        list: Daftar string, di mana setiap string adalah path lengkap ke file MP3 lokal.
    """
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    print("Mengambil data lagu dari Google Sheets CSV...")
    try:
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
        # Menggunakan io.StringIO untuk membaca data CSV dari memori.
        csv_data = io.StringIO(response.content.decode('utf-8'))
        reader = csv.DictReader(csv_data)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error saat mengambil file CSV: {e}")
        return []

    local_mp3_files = []

    for row in reader:
        # Memeriksa baris yang valid (NomorLagu tidak '000' dan ada)
        if row.get('NomorLagu') == '000' or not row.get('NomorLagu'):
            continue

        nomor = row.get('NomorLagu').zfill(3)
        judul = clean_filename(row.get('JudulLagu'))
        media_link = row.get('MediaLink', '').strip()

        if not media_link or not media_link.endswith('.mp3'):
            continue

        mp3_filename = f"KRI_{nomor}_{judul}.mp3"
        mp3_path = os.path.join(DOWNLOAD_DIR, mp3_filename)

        # 1. DOWNLOAD MP3 (JIKA BELUM ADA)
        if not os.path.exists(mp3_path):
            print(f"  > Mendownload: {mp3_filename}...")
            try:
                mp3_response = requests.get(media_link, stream=True, timeout=60)
                mp3_response.raise_for_status()
                with open(mp3_path, 'wb') as f:
                    for chunk in mp3_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                local_mp3_files.append(mp3_path)
            except requests.exceptions.RequestException as e:
                print(f"  > ⚠️ GAGAL mendownload MP3 {mp3_filename}: {e}")
                continue
        else:
            # Menggunakan os.path.join agar urutan penggabungan tetap benar
            local_mp3_files.append(mp3_path)
            print(f"  > Sudah ada, dilewati: {mp3_filename}")

    # Mengurutkan file berdasarkan nama untuk memastikan urutan lagu yang benar.
    local_mp3_files.sort()
    return local_mp3_files


def create_zip_archive(file_list):
    """
    Membuat file ZIP dari daftar path file MP3 lokal.

    Args:
        file_list (list): Daftar path lengkap ke file MP3 yang akan di-ZIP.
    """
    print("\n" + "="*50)
    print(f"Memulai Proses 1: Mengkompres {len(file_list)} file ke ZIP...")
    zip_path = os.path.join(DOWNLOAD_DIR, ZIP_FILENAME)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_list:
                # Menggunakan jalur relatif untuk membuat file di dalam ZIP lebih rapi
                zipf.write(file_path, os.path.relpath(file_path, DOWNLOAD_DIR))

        print(f"🎉 Kompresi selesai! File ZIP tersedia di: {zip_path}")
    except Exception as e:
        print(f"❌ GAGAL saat membuat file ZIP. Detail: {e}")

    print("="*50)


def merge_mp3_files(file_list):
    """
    Menggabungkan semua file MP3 menjadi satu file MP3 besar.

    Args:
        file_list (list): Daftar path lengkap ke file MP3 yang akan digabungkan.
    """
    print("\n" + "="*50)
    print(f"Memulai Proses 2: Menggabungkan {len(file_list)} file MP3...")

    if not file_list:
        print("❌ Tidak ada file MP3 yang dapat digabungkan.")
        return

    # Inisialisasi AudioSegment kosong
    final_audio = AudioSegment.empty()

    try:
        # Jeda 1 detik (1000 milidetik) antar lagu
        silence = AudioSegment.silent(duration=1000)

        for i, file_path in enumerate(file_list):
            print(f"  > Menggabungkan [{i+1}/{len(file_list)}]: {os.path.basename(file_path)}")
            # Muat file MP3 menggunakan pydub
            song = AudioSegment.from_mp3(file_path)
            final_audio += song
            # Tambahkan jeda (kecuali lagu terakhir)
            if i < len(file_list) - 1:
                final_audio += silence

        gabungan_path = os.path.join(DOWNLOAD_DIR, GABUNGAN_FILENAME)
        print(f"\n  > Mengekspor ke {GABUNGAN_FILENAME} (membutuhkan waktu)...")
        # Ekspor audio yang sudah digabungkan
        final_audio.export(gabungan_path, format="mp3")

        print(f"🎉 Penggabungan selesai! File MP3 gabungan tersedia di: {gabungan_path}")

    except FileNotFoundError:
        print(f"❌ GAGAL saat penggabungan. Pastikan FFmpeg atau Libav terinstal dan dapat diakses di PATH Anda.")
        print("Detail: Pydub mengandalkan library eksternal ini untuk memproses MP3.")
        sys.exit(1) # Keluar dengan kode error
    except Exception as e:
        print(f"❌ GAGAL saat penggabungan. Error tak terduga: {type(e).__name__}")
        print(f"Detail Error: {e}")

    print("="*50)


#  3. EKSEKUSI UTAMA 

if __name__ == "__main__":
    print(f"--- Skrip Kidung Reformed Injili Downloader & Merger ---")

    # Langkah 1: Download semua file MP3
    list_file_mp3 = download_mp3_and_get_list()

    if list_file_mp3:
        # Langkah 2: Kompres ke ZIP
        create_zip_archive(list_file_mp3)

        # Langkah 3: Gabungkan menjadi 1 MP3
        merge_mp3_files(list_file_mp3)
    else:
        print("\n❌ Tidak ada file MP3 yang berhasil diunduh. Proses dihentikan.")
        sys.exit(1)