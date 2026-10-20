# Valuasi DCF ICBP dan Studi Eksposur Valas

> **Analisis edukasi, bukan nasihat investasi.** Tidak ada isi repositori ini yang merupakan rekomendasi untuk membeli, menjual, atau menahan saham.

*Awalnya tugas kuliah Financial Management; dibangun ulang dan dikembangkan dalam Python.*

[English](README.md) | Bahasa Indonesia

## Ringkasan

Repositori ini menilai **PT Indofood CBP Sukses Makmur Tbk (IDX: ICBP)** dengan model arus kas terdiskonto (DCF) yang
transparan dan teruji (35 tes pytest), serta mengaudit workbook Excel aslinya. Isi: proyeksi FCFF 5 tahun, WACC (CAPM),
terminal value (Gordon growth dan exit multiple), nilai per saham, heatmap sensitivitas WACC x g, skenario bull/base/bear,
reverse DCF, dan modul kedua yang lebih singkat tentang eksposur valas (kasus **fiktif** dengan angka ilustratif).

## Hasil utama

Tanggal valuasi 31 Des 2025. Harga pasar **Rp7.650** sesuai catatan di workbook kuliah (Mei 2026, tidak diperbarui).

| | Nilai per saham (Rp) | vs Rp7.650 |
|---|---:|---:|
| Workbook Excel asli | 20.397 | +167% |
| **Model lanjutan, base** (rata-rata Gordon dan exit multiple) | **13.816** | **+81%** |
| Model lanjutan, bear | 8.025 | +5% |
| Model lanjutan, bull | 21.979 | +187% |

- Hasil sangat sensitif terhadap metode terminal value: Gordon (base) Rp17.301 vs exit multiple 7,0x Rp10.330.
- Multiple EV/EBITDA yang tersirat di pasar sekitar 6,75x; terminal value Gordon pada base case setara 12,6x.
- Reverse DCF: harga pasar setara WACC sekitar 14-15% pada asumsi operasional base (base case: 9,3%).

## Verifikasi terhadap Excel

Replika Python atas sheet *FCFF & DCF* cocok dengan Excel: **26 dari 26 keluaran sama** (selisih relatif terbesar 3e-10).
Artinya hitungan Excel benar secara aritmetika; perbedaan dengan model lanjutan berasal dari pilihan pemodelan.

## Temuan audit workbook (ringkas)

1. "NWC" mencakup kas, investasi jangka pendek, dan utang jangka pendek, sehingga FCFF FY2025 terlalu rendah (5,47 tn vs 9,04 tn dengan NWC operasi).
2. NWC FY2022 di-hardcode tanpa sumber di dalam rumus.
3. Ekuitas = EV - net debt saja; kepentingan non-pengendali (22,2 tn) tidak dikurangkan dan asosiasi (7,4 tn) tidak ditambahkan.
4. Pertumbuhan terminal 5% melebihi proksi risk-free 4,75%; selisih WACC - g hanya 2,26 pp.
5. Risk-free memakai BI Rate (bukan yield obligasi jangka panjang); biaya ekuitas 9,25% tergolong rendah.
6. Neraca FY2023 dan FY2024 tidak seimbang (selisih 100 dan 75.521 juta).
7. Baris verifikasi DOL/DFL di workbook bertentangan dengan rumusnya; DOL didefinisikan sebagai laba bruto / EBIT.
8. Sheet valas memakai akar 365 hari, menjumlahkan VaR tanpa korelasi; P&L at risk 73% laba bersih turun menjadi 61% dengan akar 252.
9. Teks rekomendasi tidak konsisten dengan sel (mis. "Target DCF 12.000+" vs 20.397).
10. Kemungkinan D&A terhitung ganda di arus kas operasi (ditandai, belum dikonfirmasi).

## Keterbatasan

Angka laporan keuangan diambil dari workbook mata kuliah yang bersumber dari laporan tahunan ICBP / IDX filings dan belum
diverifikasi ulang ke dokumen aslinya. Harga pasar tidak diperbarui. Penyesuaian WACC +2,0 pp dan seluruh driver skenario
adalah asumsi analis. Studi valas sepenuhnya fiktif.

## Cara menjalankan

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt && pip install -e .
python -m icbp_valuation        # verifikasi, skenario, gambar, tabel
pytest -q                       # 35 tes
python scripts/build_notebooks.py
```

Semua asumsi ada di `assumptions.yaml`.

## Pengungkapan bantuan AI

Repositori ini dibangun ulang dari workbook tugas kuliah penulis dengan bantuan besar dari asisten AI (Claude, Anthropic,
melalui Claude Code) untuk kode, tes, notebook, dokumentasi, audit workbook, serta usulan asumsi model lanjutan. Perusahaan,
tugas asli, dan data sumber berasal dari penulis. Asumsi bersifat judgemental dan perlu ditinjau pengguna model.

## Disclaimer

**Analisis edukasi, bukan nasihat investasi.** Lisensi MIT (lihat [LICENSE](LICENSE)).
