"""
measure_score_distribution.py
------------------------------
Script untuk mengukur distribusi skor similarity dari FAISS vector store.

Mengukur min/median/max untuk:
- Query in-domain (mengandung keyword BPJS/BPU)
- Query off-domain (tidak ada keyword domain)

USAGE:
    python measure_score_distribution.py
"""

import statistics
from sapa.chatbot import load_retriever, DOMAIN_KEYWORDS

# Sample queries untuk baseline measurement
IN_DOMAIN_QUERIES = [
    "Apa itu program BPU?",
    "Bagaimana cara daftar BPJS Ketenagakerjaan?",
    "Berapa iuran JKK untuk pekerja mandiri?",
    "Siapa yang bisa ikut program magang BPJS TK?",
    "Apa manfaat dari Jaminan Hari Tua?",
    "Gimana cara klaim JKK kalau kecelakaan kerja?",
    "Dokumen apa saja yang perlu untuk pendaftaran BPU?",
    "Kapan iuran BPJS harus dibayar?",
]

OFF_DOMAIN_QUERIES = [
    "Berapa harga bitcoin hari ini?",
    "Siapa presiden Indonesia?",
    "Bagaimana cara memasak nasi goreng?",
    "Kapan perang dunia kedua berakhir?",
    "Apa ibu kota Prancis?",
    "Jelaskan tentang fotosintesis",
    "Berapa jarak bumi ke bulan?",
    "Siapa penemu lampu pijar?",
]


def measure_distribution(queries, label):
    """Ukur distribusi skor similarity untuk list query."""
    print(f"\n{'='*60}")
    print(f"MENGUKUR: {label}")
    print(f"{'='*60}")
    
    retriever = load_retriever()
    vector_store = retriever.vectorstore
    
    all_scores = []
    
    for query in queries:
        try:
            scored_docs = vector_store.similarity_search_with_relevance_scores(query, k=5)
            if scored_docs:
                scores = [score for _, score in scored_docs]
                all_scores.extend(scores)
                print(f"✓ '{query[:50]}...' → Top score: {max(scores):.4f}")
            else:
                print(f"✗ '{query[:50]}...' → Tidak ada hasil")
        except Exception as e:
            print(f"✗ '{query[:50]}...' → Error: {e}")
    
    if all_scores:
        print(f"\n📊 DISTRIBUSI SKOR ({len(all_scores)} dokumen dari {len(queries)} query):")
        print(f"   MIN:    {min(all_scores):.4f}")
        print(f"   MEDIAN: {statistics.median(all_scores):.4f}")
        print(f"   MEAN:   {statistics.mean(all_scores):.4f}")
        print(f"   MAX:    {max(all_scores):.4f}")
        
        # Hitung berapa persen yang lolos threshold
        from sapa.chatbot import MIN_RELEVANCE_SCORE
        above_threshold = sum(1 for s in all_scores if s >= MIN_RELEVANCE_SCORE)
        print(f"\n   Skor >= {MIN_RELEVANCE_SCORE} (MIN_RELEVANCE_SCORE): {above_threshold}/{len(all_scores)} ({100*above_threshold/len(all_scores):.1f}%)")
        
        return {
            "min": min(all_scores),
            "median": statistics.median(all_scores),
            "mean": statistics.mean(all_scores),
            "max": max(all_scores),
            "count": len(all_scores),
            "above_threshold": above_threshold,
        }
    else:
        print(f"\n⚠️ Tidak ada skor yang berhasil diukur!")
        return None


def main():
    print("="*60)
    print("BASELINE: DISTRIBUSI SKOR SIMILARITY SEARCH")
    print("="*60)
    print(f"Normalisasi embedding: AKTIF (encode_kwargs={{'normalize_embeddings': True}})")
    print(f"FAISS metric: Cosine similarity (METRIC_INNER_PRODUCT dengan embedding normalized)")
    
    try:
        in_domain_stats = measure_distribution(IN_DOMAIN_QUERIES, "QUERY IN-DOMAIN")
        off_domain_stats = measure_distribution(OFF_DOMAIN_QUERIES, "QUERY OFF-DOMAIN")
        
        print("\n" + "="*60)
        print("RINGKASAN BASELINE")
        print("="*60)
        
        if in_domain_stats and off_domain_stats:
            print(f"In-domain median:  {in_domain_stats['median']:.4f}")
            print(f"Off-domain median: {off_domain_stats['median']:.4f}")
            print(f"Gap (in - off):    {in_domain_stats['median'] - off_domain_stats['median']:.4f}")
            print("\n✅ Semakin besar gap, semakin baik separasi domain.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
