# Your knowledge database

from generic import *
import urllib2, datetime
import xml.dom.minidom as minidom

ARXIV_QUERY_URL = "http://export.arxiv.org/api/query?id_list="
ARXIV_RE = r'^[0-9]{4}\.[0-9]{4}$'

DOI_RE = r''
SOFTWARE_RE = r''
WEBPAGE_RE = r''


## Data Models ##

# This is a site-wide repository.
class KnowledgeItems(db.Model):
    species = db.StringProperty(required = True)
    identifier = db.StringProperty(required = True)
    metadata = db.ReferenceProperty(required = True)           # Must refer to one of arXiv, PublishedArticles, Software, etc...
    

# Specific knowledge items.
class arXiv(db.Model):
    item_id = db.StringProperty(required = True)
    title = db.StringProperty(required = True)
    authors = db.StringListProperty(required = True)
    date = db.DateTimeProperty(required = True)
    abstract = db.TextProperty(required = False)       # Are there articles without abstract?
    link = db.LinkProperty(required = True)


class PublishedArticles(db.Model):
    item_id = db.StringProperty(required = True)


class Software(db.Model):
    item_id = db.StringProperty(required = True)


class WebPage(db.Model):
    item_id = db.StringProperty(required = True)


# This is user-specific. Each of these items should have as parent the current user.
class LibraryItems(db.Model):
    item = db.ReferenceProperty(required = True)
    added = db.DateTimeProperty(auto_now_add = True)
    tags = db.StringListProperty(required = True)    # Must be required=True, however it can default to an empty list.


# Each review should have as parent one of KnowledgeItems.
class Reviews(db.Model):
    author = db.ReferenceProperty(required = True)
    review = db.TextProperty(required = True)
    date = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)


## Helper functions ##

def arXiv_metadata(arXiv_id):
    tree = minidom.parseString(urllib2.urlopen(ARXIV_QUERY_URL + arXiv_id).read().replace("\n", ""))
    params = {}
    params["item_id"] = arXiv_id
    params["title"] = tree.getElementsByTagName("entry")[0].getElementsByTagName("title")[0].childNodes[0].nodeValue
    params["authors"] = []
    for author in tree.getElementsByTagName("author"):
        author_name = author.getElementsByTagName("name")[0].childNodes[0].nodeValue
        params["authors"].append(author_name)
    date_string = tree.getElementsByTagName("published")[0].childNodes[0].nodeValue
    params["date"] = datetime.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
    params["abstract"] = tree.getElementsByTagName("summary")[0].childNodes[0].nodeValue
    params["link"] = tree.getElementsByTagName("entry")[0].getElementsByTagName("id")[0].childNodes[0].nodeValue
    return params
    

# For the add_new_X functions, X should match the database's name. They must return the item just added.
def add_new_arXiv(identifier):
    params = arXiv_metadata(identifier)
    new = arXiv(**params)
    logging.debug("DB WRITE: Adding new arXiv article :1", identifier)
    new.put()
    return new

def add_new_PublishedArticle(identifier):
    pass

def add_new_Software(identifier):
    pass

def add_new_WebPage(identifier):
    pass

def get_add_KnowledgeItem(species, identifier):
    """Returns a KnowledgeItem of the given species and identifier. If it doesn't exist, create it."""
    if species == "arXiv": db_name = "arXiv"
    elif species == "article": db_name = "PublishedArticle"
    elif species == "software": db_name = "Software"
    elif species == "webpage": db_name = "WebPage"
    else:
        logging.error("Wrong KnowledgeItem species: %s" % species)
        assert False

    logging.debug("DB READ: Checking if %s item exists in KnowledgeItems." % db_name)
    q = db.GqlQuery("SELECT * FROM %s WHERE item_id = %s" % (db_name, identifier)).get()
    if q: return q
    return eval('add_new_%s("%s")' % (db_name, identifier))
    
    

def add_KnowledgeItem_to_library(username, item):
    pass

    


## Handlers ##

class MainPage(GenericPage):
    def get(self):
        self.write("library's main page.")


class Articles(GenericPage):
    def get(self):
        self.write("Your articles in the knowledge database.")


class BlogPosts(GenericPage):
    def get(self):
        self.write("Your blog posts in the knowledge database.")


class Software(GenericPage):
    def get(self):
        self.write("Your software in the knowledge database.")


class New(GenericPage):
    def get(self):
        username = self.get_username()
        self.render("new_knowledge.html")

    def post(self):
        username = self.get_username()
        if not username: self.redirect("/login")
        species = self.request.get('species')
        identifier = self.request.get('identifier')
        have_error = False
        params = {}

        if species == "arXiv":
            if not re.match(ARXIV_RE, identifier):
                params['error'] = "That's not a valid arXiv id."
                have_error = True
        elif species == "article":
            if not re.match(DOI_RE, identifier):
                params['error'] = "That's not a valid DOI."
                have_error = True
        elif species == "software":
            if not re.match(SOFTWARE_RE, identifier):
                params['error'] = "That's not a valid url."
                have_error = True
        elif species == "webpage":
            if not re.match(WEBPAGE_RE, identifier):
                params['error'] = "That's not a valid url."
                have_error = True
        else:
            logging.error("Unknown species for new KnowledgeItem: %s" % species)
            params['error'] = "There was an error processing your request."
            have_error = True

        if have_error:
            self.render("new_knowledge.html", **params)
        else:
#            try:
            item = get_add_KnowledgeItem(species, identifier)  # Retrieves the item. If it's not present, adds it.
            add_KnowledgeItem_to_library(username, item)
            self.redirect("/library/item/%s" % str(item.key().id()))
#            except:
#                params['error'] = "Could not retrieve " + species
#                self.render("new_knowledge.html", **params)


class Item(GenericPage):
    def get(self, item_id):
        username = self.get_username()
        if not username: self.redirect("/login")
        self.write(item_id)