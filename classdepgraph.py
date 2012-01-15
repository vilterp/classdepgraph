from BeautifulSoup import BeautifulSoup, NavigableString
import sys
import urllib
import re
import pydot
import codecs

def read_url(url):
  f = urllib.urlopen(url)
  return f.read()

def get_all_majors():
  url = 'http://collegecatalog.uchicago.edu/thecollege/programsofstudy/'
  doc = BeautifulSoup(read_url(url))
  major_links = doc.find('ul', {'class':'menu'}).li.ul.li.ul.findAll('a')
  link_map = {}
  for a in major_links:
    link_map[a.text] = 'http://collegecatalog.uchicago.edu' + a['href']
  return link_map

def trace(foo):
  print >> sys.stderr, foo

# url -> Map[Course Name, Course Dict]
def get_courses(url):
  doc = BeautifulSoup(read_url(url))
  course_elems = doc.findAll('div', {'class': 'courseblock main'})
  courses = {}
  for course_elem in course_elems:
    title_text = course_elem.find('p', {'class':'courseblocktitle'}).strong.text
    elems = [s.strip() for s in title_text.split('.')]
    try:
      (code, title, credit, _) = elems
    except ValueError:
      trace('=' * 20 + ' PASS: %s' % elems)
      continue
    details = course_elem.find('p', {'class': 'courseblockdetail'})
    texts = [x.strip() for x in details.contents if x.__class__ == NavigableString]
    prereqs = None
    notes = None
    equivs = None
    for text in texts:
      # scrape rereqs
      m = re.search(r'Prerequisite\(s\): (.*)', text)
      if m:
        prereq_text = m.group(1)
        res = re.findall(r'([A-Z]{4} [0-9]{5})+', prereq_text)
        if len(res) > 0:
          prereqs = res
        else:
          prereqs = prereq_text
      # scrape note
      m = re.search(r'Note\(s\): (.*)', text)
      if m:
        notes = m.group(1)
      # scrape equivalent courses
      m = re.findall(r'Equivalent Course\(s\): ([A-Z]{4} [0-9]{5})', text)
      if len(m) > 0:
        equivs = m
    course = {'code': code.replace('&#160;', ' '), 'title': title, 'prereqs': prereqs, 'notes': notes, 'equivs': equivs}
    courses[title] = course
  return courses

# () -> Map[Major, Map[Course title, Course dict]]
def get_all_courses():
  all_courses = {}
  for major, url in get_all_majors().iteritems():
    print major
    all_courses[major] = get_courses(url)
  return all_courses

def write_courses(courses):
  f = open('courses.py', 'w')
  f.write(str(courses))
  f.close()

def read_courses():
  f = open('courses.py')
  return eval(f.read())

# Map[Major, Map[Course title, Course dict]] -> Map[Course title, course dict w/ multiple codes]
def resolve_equivalents(courses):
  by_code = {} # Map[course id, course dict]
  for major, courses_dict in courses.iteritems():
    for title, course_dict in courses_dict.iteritems():
      by_code[course_dict['code']] = course_dict
  by_title = {}
  for major, courses_dict in courses.iteritems():
    for title, course_dict in courses_dict.iteritems():
      if title not in by_title:
        by_title[title] = course_dict
        prereqs_by_title = []
        if type(course_dict['prereqs']) == list:
          for code in course_dict['prereqs']:
            try:
              title = by_code[code]['title']
              prereqs_by_title.append(title)
            except KeyError:
              trace('NOT FOUND: %s' % code)
          del course_dict['prereqs']
          course_dict['prereqs'] = prereqs_by_title
        code = course_dict['code']
        course_dict['codes'] = [code]
        del course_dict['code']
      else:
        by_title[title]['codes'].append(course_dict['code'])
  return by_title

def get_all_courses_cached():
  courses = None
  try:
    courses = read_courses()
  except IOError:
    courses = get_all_courses()
    write_courses(courses)
  return courses

# Map[Course title, course dict w/ multiple codes] -> pydot.Graph
def build_graph(courses):
  g = pydot.Graph('courses', graph_type='digraph')
  i = 0
  title_to_id = {}
  for title, course in courses.iteritems():
    course_id = 'node' + str(i)
    i += 1
    course['node_id'] = course_id
    title_to_id[course['title']] = course_id
    g.add_node(pydot.Node(course_id, label=title))
  for title, course in courses.iteritems():
      if course['prereqs']:
        if type(course['prereqs']) == list:
          for prereq in course['prereqs']:
            g.add_edge(pydot.Edge(title_to_id[course['title']], title_to_id[prereq]))
        else:
          trace('prereqs are wrong: %s' % course['prereqs'])
  return g

if __name__ == '__main__':
  dot = build_graph(resolve_equivalents(get_all_courses_cached())).to_string()
  f = codecs.open('classdepgraph.dot', 'w', encoding='utf-8')
  f.write(dot)
  f.close()
