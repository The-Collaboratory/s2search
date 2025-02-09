import os
import pickle
import numpy as np
from s2search.text import fix_text, fix_author_text
from s2search.features import make_features, posthoc_score_adjust
from multiprocessing import Pool, cpu_count


class S2Ranker:
    """A class to encapsulate the Semantic Scholar search ranker.

    Arguments:
        data_dir {str} -- where the language models and lightgbm model live.
        use_posthoc_correction {bool} -- whether to use posthoc correction
    """
    def __init__(self, data_dir, use_posthoc_correction=True):
        self.use_posthoc_correction = use_posthoc_correction
        self.data_dir = data_dir        
        with open(os.path.join(data_dir, 'lightgbm_model.pickle'), 'rb') as f:
            self.model = pickle.load(f)

        self.pool = Pool(cpu_count())
    
    def score(self, query, papers):
        """Score each pair of (query, paper) for all papers

        Arguments:
            query {str} -- plain text search query 
            papers {list of dicts} -- A list of candidate papers, each of which
                                      is a dictionary.

        Returns:
            scores {np.array} -- an array of scores, one per paper in papers
        """
        query = str(query)
        #presults = [self.prepare_result(paper) for paper in papers]
        presults = self.pool.map(self.prepare_result,papers)
        args = [(query,pr) for pr in presults]
        feats = self.pool.starmap(make_features, args)
        X = np.array(feats)
        

        scores = self.model.predict(X)
        if self.use_posthoc_correction:
            scores = posthoc_score_adjust(scores, X, query)
        return scores
    
    @classmethod
    def prepare_result(cls, paper):
        """Prepare the raw text result for featurization

        Arguments:
            paper {dict} -- A dictionary that has the required paper fields:
                            'title', 'abstract', 'authors', 'venues', 'year',
                            'n_citations', 'n_key_citations'
        Returns:
            out {dict} -- A dictionary where the paper fields have been pre-processed.
        """
        out = {'paper_year': paper.get('year', np.nan)}
        out['n_citations'] = paper.get('n_citations', 0)
        # if n_key_citations aren't available, we can get a quick estimate of what they are from the n_citations
        out['n_key_citations'] = paper.get('n_key_citations', int(-1.4 + np.log1p(out['n_citations'])))
        if out['n_key_citations'] < 0:
            out['n_key_citations'] = 0
        out['paper_title_cleaned'] = fix_text(paper.get('title', ''))
        out['paper_abstract_cleaned'] = fix_text(paper.get('abstract', ''))
        out['paper_venue_cleaned'] = fix_text(paper.get('venue', ''))
        out['author_name'] = [fix_author_text(i) for i in paper.get('authors', [])]
        return out
