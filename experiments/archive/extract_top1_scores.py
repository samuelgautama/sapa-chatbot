#!/usr/bin/env python3
"""Extract top-1 scores per retrieval query untuk kalibrasi threshold dua tingkat."""

import json
from sapa.chatbot import load_retriever

def main():
    ret = load_retriever()
    vs = ret.vectorstore
    cases = json.load(open('evaluation/evaluation_dataset.json', 'r', encoding='utf-8'))
    
    top1_scores = []
    
    for c in cases:
        if c.get('category') in {'retrieval', 'context'}:
            try:
                scored = vs.similarity_search_with_relevance_scores(c['question'], k=1)
                if scored:
                    score = scored[0][1]
                    top1_scores.append({
                        'id': c['id'],
                        'question': c['question'],
                        'score': float(score),
                        'keywords': c.get('expected_keywords', [])
                    })
            except:
                pass
    
    top1_scores = sorted(top1_scores, key=lambda x: x['score'], reverse=True)
    
    print(f"Total retrieval queries: {len(top1_scores)}")
    print(f"Min score: {top1_scores[-1]['score']:.4f}")
    print(f"Max score: {top1_scores[0]['score']:.4f}")
    print(f"Median score: {top1_scores[len(top1_scores)//2]['score']:.4f}")
    print(f"Q1 (25%): {top1_scores[len(top1_scores)//4]['score']:.4f}")
    print(f"Q3 (75%): {top1_scores[3*len(top1_scores)//4]['score']:.4f}")
    
    # Simpan untuk analisis manual
    with open('top1_scores_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(top1_scores, f, ensure_ascii=False, indent=2)
    
    print("\nTop 10 scores (potential High gate):")
    for item in top1_scores[:10]:
        print(f"  {item['id']}: {item['score']:.4f} — {item['question'][:50]}")
    
    print("\nBottom 10 scores (potential Low gate):")
    for item in top1_scores[-10:]:
        print(f"  {item['id']}: {item['score']:.4f} — {item['question'][:50]}")

if __name__ == "__main__":
    main()
