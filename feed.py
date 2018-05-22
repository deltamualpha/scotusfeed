import io
import re
import requests
import argparse
import logging
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from dateutil import parser
from datetime import timezone
from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine

def feedbase():
  fg = FeedGenerator()
  fg.load_extension('podcast')
  fg.title('SCOTUS Audio ' + TERM + 'Term')
  fg.subtitle('This is an automated feed of the mp3 files from the SCOTUS website. NOT AFFILIATED WITH THE COURT OR THE JUSTICES.')
  fg.link(href=LINK, rel='self')
  fg.language('en')
  if HOME:
    fg.link(href=HOME, rel='alternate')
  if LOGO:
    fg.logo(LOGO)
  return fg

def get_filesize(argument_id):
  return requests.head('https://www.supremecourt.gov/media/audio/mp3files/' + argument_id + '.mp3').headers['content-length']

def add_argument(feed, argument_id, argument_number, argument_title, argument_date, docket_number):
  fe = feed.add_entry(order='append')
  url = "https://www.supremecourt.gov/oral_arguments/audio/" + TERM + "/" + argument_id
  fe.id(url)
  fe.title(argument_number + ": " + argument_title)
  fe.link(href=url)
  fe.enclosure('https://www.supremecourt.gov/media/audio/mp3files/' + argument_id + '.mp3', get_filesize(argument_id), 'audio/mpeg')
  fe.published(argument_date)
  fe.description(parse_qp(argument_number) + "\nThe Supreme Court docket for this case is available at https://www.supremecourt.gov/docket/docketfiles/html/public/" + docket_number + ".html.")

def parse_qp(docket_number):
  if "-Orig" in docket_number:
    docket = docket_number.split("-")[0] + ' orig'
  else:
    split_docket = docket_number.split("-")
    docket = '{term}-{num:05d}'.format(term=split_docket[0], num=int(split_docket[1]))

  fp = io.BytesIO(requests.get("https://www.supremecourt.gov/qp/" + docket + "qp.pdf").content)
  parser = PDFParser(fp)
  doc = PDFDocument()
  parser.set_document(doc)
  doc.set_parser(parser)
  doc.initialize('')
  rsrcmgr = PDFResourceManager()
  laparams = LAParams()
  laparams.char_margin = 1.0
  laparams.word_margin = 1.0
  device = PDFPageAggregator(rsrcmgr, laparams=laparams)
  interpreter = PDFPageInterpreter(rsrcmgr, device)
  extracted_text = ''

  for page in doc.get_pages():
    interpreter.process_page(page)
    layout = device.get_result()
    for lt_obj in layout:
      if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
        text = lt_obj.get_text().replace("(cid:160)", " ")
        if ("LOWER COURT CASE NUMBER:" not in text) and ("DECISION BELOW:" not in text):
          extracted_text += text

  return re.sub(' +', ' ', extracted_text)

def parse_sessions(feed, sessions):
  for session in sessions:
    for argument in session.find_all("tr")[:0:-1]: # pop off the header and invert
      argument_number = argument.a.string
      if "-Orig" in argument_number:
        # magic docket number for now, see
        # https://www.cocklelegalbriefs.com/blog/supreme-court/the-u-s-supreme-courts-use-of-docket-numbers/
        docket_number = "22o" + argument_number.split("-")[0]
      elif "-Question-" in argument_number:
        # special case for two-part Obergefell v. Hodges argument
        docket_number = "-".join(argument_number.split("-")[0:2])
      else:
        docket_number = argument_number

      argument_id = argument.a['href'].split("/")[-1]
      argument_title = argument.find_all("span")[1].string
      argument_date = parser.parse(argument.find_all("td")[1].string).replace(tzinfo=timezone.utc)
      add_argument(feed, argument_id, argument_number, argument_title, argument_date, docket_number)

if __name__ == "__main__":
  # disable python root logger because of pdfminer spam
  # https://stackoverflow.com/questions/29762706/warnings-on-pdfminer
  logging.propagate = False 
  logging.getLogger().setLevel(logging.ERROR)

  # argparse
  args = argparse.ArgumentParser(description='Generate an RSS feed for a particular term of the court.')
  args.add_argument('--term', required=True, help="The term to generate the feed for.")
  args.add_argument('--link', required=True, help="The URL of the completed feed.")
  args.add_argument('--home', help="The landing page for the source of the audio. Suggested if using a logo.")
  args.add_argument('--logo', help="The URL of a logo for the feed.")
  arglist = args.parse_args()

  TERM = arglist.term
  LINK = arglist.link
  LOGO = arglist.logo
  HOME = arglist.home

  content = requests.get("https://www.supremecourt.gov/oral_arguments/argument_audio/" + TERM).content
  sessions = BeautifulSoup(content, "html.parser").find_all("table", class_="table table-bordered")
  feed = feedbase()
  parse_sessions(feed, sessions)
  print(feed.rss_str(pretty=True).decode('utf-8'))
