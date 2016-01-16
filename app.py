from operator import itemgetter
import psycopg2
import psycopg2.extras
from flask import Flask
from flask import render_template
from flask import request
from gensim.models import Doc2Vec
import re
import argparse

app = Flask(__name__)


"""Helpers"""
def get_subjects():
    cur = conn.cursor()
    query = "SELECT subject, count(*) FROM articles group by subject;"
    cur.execute(query)
    subjects = sorted(cur.fetchall(), key=lambda tup:tup[0])
    return subjects

def get_articles(indices):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        query = cur.mogrify("SELECT * FROM articles WHERE index IN %s ORDER BY last_submitted DESC", (tuple(indices),))
        cur.execute(query)
        articles = cur.fetchall()
        return articles

def get_articles_by_subject(subject):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        query = "SELECT * FROM articles WHERE subject='" + subject + "' ORDER BY last_submitted DESC"
        cur.execute(query)
        articles = cur.fetchall()
        return articles

def get_article(index):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        query = "SELECT * FROM articles WHERE index="+str(index)
        cur.execute(query)
        article = cur.fetchone()
        return article

@app.route('/viz')
def viz():
    return render_template("louvain.html")

@app.route('/')
@app.route('/subjects/')
@app.route('/subjects/<subject>')
def browse_subjects(subject=None):
    if subject is None:
        return render_template("browse.html", subjects=get_subjects())
    else:
        articles = get_articles_by_subject(subject)
        return render_template("articles.html", articles=articles, subject=subject)

@app.route('/article/<main_article_id>')
def find_similars(main_article_id=None):
    main_article = get_article(main_article_id)
    sims = model.docvecs.most_similar(int(main_article_id)) # list of (id, similarity)
    sim_articles = get_articles([int(index) for index, sim in sims]) # list of dictionaries...
    # we're gonna add similarity scores to each dictionary (article) in above list from sims
    sort_these = []
    for article in sim_articles:
        sim_score = [score for idx, score in sims if article['index'] == idx ][0]
        article.extend([round(sim_score, 2)])
        sort_these.append(article)

    # sort the list of dictionaries by value
    # sorted_articles = sorted(sort_these, key=itemgetter('similarity'))

    return render_template("doc.html", main_article=main_article, sims=sort_these)

@app.route('/search', methods=['POST'])
def search():
    if request.method == 'POST':
        query = request.form['search']
        q_vec = model.infer_vector(query.split())
        results = model.docvecs.most_similar(positive=[q_vec], topn=100)
        results = [int(r[0]) for r in results]
        results = get_articles(results)
        return render_template("search.html", articles=results)



if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='Fire up flask server with appropriate model')
    parser.add_argument('model_path', help="Name of model file")
    args = parser.parse_args()

    # load model:
    model = Doc2Vec.load(args.model_path)

    # run app in db connection context
    with psycopg2.connect(dbname='arxiv') as conn:
        app.run(host='0.0.0.0', debug=True)