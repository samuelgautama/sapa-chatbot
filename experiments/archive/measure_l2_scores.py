#!/usr/bin/env python3
"""Ukur distribusi skor L2 FAISS untuk in-domain vs off-domain."""

import json
from chatbot import load_retriever

def main():
    ret = load_retriever()
    vs = ret.vectorstore
    cases = json.load(open('evaluation_dataset.json', 'r', encoding='utf-8'))
    
    in_d = []
    off_d = []
    
    for c in cases:
        if c.get('category') == 'retrieval':
            try:
                scored = vs.similarity_search_with_relevance_scores(c['question'], k=1)
                if scored:
                    in_d.append(scored[0][1])
            except:
                pass
        elif c.get('category') in {'fallback'}:  # off-domain dalam fallback category
            try:
                scored = vs.similarity_search_with_relevance_scores(c['question'], k=1)
                if scored:
                    off_d.append(scored[0][1])
            except:
                pass
    
    in_d = sorted(in_d)
    off_d = sorted(off_d)
    
    if in_d:
        print(f"In-domain (retrieval): n={len(in_d)}, min={in_d[0]:.4f}, max={in_d[-1]:.4f}, median={in_d[len(in_d)//2]:.4f}")
    if off_d:
        print(f"Off-domain (fallback): n={len(off_d)}, min={off_d[0]:.4f}, max={off_d[-1]:.4f}, median={off_d[len(off_d)//2]:.4f}")

if __name__ == "__main__":
    main()

