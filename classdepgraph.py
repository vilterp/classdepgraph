from BeautifulSoup import BeautifulSoup, NavigableString
import sys
import urllib
import re
import pydot
import codecs

# TODO:
# - parse sequences
# - group courses by major
# - make sure equivalents are being handled correctly
# - include descriptions somehow
# etc...

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
    # TODO: parse sequences
    try:
      (code, title, credit, _) = elems
    except ValueError:
      trace('=' * 20 + ' PASS: %s' % elems)
      continue
    details = course_elem.find('p', {'class': 'courseblockdetail'})
    texts = [x.strip() for x in details.contents if x.__class__ == NavigableString]
    prereq_codes = []
    prereq_text = None
    notes = None
    equivs = []
    for text in texts:
      # scrape rereqs
      m = re.search(r'Prerequisite\(s\): (.*)', text)
      if m:
        prereq_text = m.group(1)
        res = re.findall(r'([A-Z]{4} [0-9]{5})+', prereq_text)
        if res:
          prereq_codes = res
      # scrape note
      m = re.search(r'Note\(s\): (.*)', text)
      if m:
        notes = m.group(1)
      # scrape equivalent courses
      m = re.findall(r'Equivalent Course\(s\): ([A-Z]{4} [0-9]{5})', text)
      if len(m) > 0:
        equivs = m
    course = {
      'code': code.replace('&#160;', ' '),
      'title': title,
      'prereq_codes': prereq_codes,
      'prereq_text': prereq_text,
      'notes': notes,
      'equivs': equivs
    }
    courses[title] = course
  return courses

# () -> Map[Major, Map[Course title, Course dict]]
def get_all_courses():
  all_courses = {}
  for major, url in get_all_majors().iteritems():
    print major
    all_courses[major] = get_courses(url)
  return all_courses

def get_all_courses_cached():
  courses = None
  try:
    courses = read_courses()
  except IOError:
    courses = get_all_courses()
    write_courses(courses)
  return courses

def write_courses(courses):
  f = open('courses.py', 'w')
  f.write(str(courses))
  f.close()

def read_courses():
  f = open('courses.py')
  return eval(f.read())

def build_datastructure(all_courses):
  majors = {} # code -> major struct
  courses = {} # title -> course struct
  for major, courses_dict in all_courses.iteritems():
    for title, course_dict in courses_dict.iteritems():
      # create major if doesn't exist
      major_code = course_dict['code'][:4]
      major_struct = None
      if major_code not in majors:
        major_struct = {
          'name': major,
          'code': major_code,
          'courses': {}
        }
        majors[major_code] = major_struct
      else:
        major_struct = majors[major_code]
      # create course struct if DNE
      course_struct = None
      if title not in courses:
        course_struct = {
          'title': title,
          'notes': course_dict['notes'],
          'prereq_codes': course_dict['prereq_codes'],
          'prereq_text': course_dict['prereq_text'],
          'desc': None,
          'major_codes': []
        }
        courses[title] = course_struct
      else:
        course_struct = courses[title]
      course_number = course_dict['code'][-5:]
      # link course with major
      has_code_struct = {
        'major': major_struct,
        'course': course_struct,
        'code': course_number,
      }
      course_struct['major_codes'].append(has_code_struct)
      majors[major_code]['courses'][course_number] = has_code_struct
  # TODO: handing equivalents correctly? do equivalent courses always have the same name?
  # link prereqs
  serialnum = 0
  for title, course_struct in courses.iteritems():
    course_struct['prereqs'] = []
    course_struct['serialnum'] = serialnum
    serialnum += 1
    for prereq in course_struct['prereq_codes']:
      major_code = prereq[:4]
      number = prereq[-5:]
      try:
        prereq_course = majors[major_code]['courses'][number]['course']
        if prereq_course not in course_struct['prereqs'] and prereq_course is not course_struct:
          course_struct['prereqs'].append(prereq_course)
      except KeyError:
        trace('missing prereq: %s %s' % (major_code, number))
    #del course_struct['prereq_codes']
  return (majors, courses)

# Map[Course title, course dict w/ multiple codes] -> pydot.Graph
def build_graph(courses):
  g = pydot.Graph('courses', graph_type='digraph')
  def get_node_name(course):
    return 'node_%d' % course['serialnum']
  
  for title, course in courses.iteritems():
    names = []
    for has_code in course['major_codes']:
      major_code = has_code['major']['code']
      course_number = has_code['code']
      names.append('%s %s' % (major_code, course_number))
    codes = '/'.join(names)
    #codes = [has_code['major']['code'] + ' ' + has_code['code'] for has_code in course['major_codes']].join('/')
    g.add_node(pydot.Node(
      get_node_name(course),
      label='%s: %s' % (codes, course['title']),
      tooltip=course['prereq_text']
    ))
    for prereq in course['prereqs']:
      g.add_edge(pydot.Edge(get_node_name(course), get_node_name(prereq)))
  return g

if __name__ == '__main__':
  raw_courses = get_all_courses_cached()
  majors, courses = build_datastructure(raw_courses)
  graph = build_graph(courses)
  f = codecs.open('classdepgraph.dot', 'w', encoding='utf-8')
  f.write(graph.to_string())
  f.close()
