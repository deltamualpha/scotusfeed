import requests
import argparse
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from dateutil import parser
from datetime import timezone

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
  fe.description("The Supreme Court docket for this case is available at https://www.supremecourt.gov/docket/docketfiles/html/public/" + docket_number + ".html.")

def parse_sessions(feed, sessions):
  for session in sessions:
    for argument in session.find_all("tr")[:0:-1]: # pop off the header and invert
      argument_number = argument.a.string
      if "-Orig" in argument_number:
        # magic docket number for now, see https://www.cocklelegalbriefs.com/blog/supreme-court/the-u-s-supreme-courts-use-of-docket-numbers/
        docket_number = "22o" + argument_number.split("-")[0]
      else if  "-Question-" in argument_number:
        # special case for two-part Obergefell v. Hodges argument
        docket_number = argument_number.split("-")[0]
      else:
        docket_number = argument_number

      argument_id = argument.a['href'].split("/")[-1]
      argument_title = argument.find_all("span")[1].string
      argument_date = parser.parse(argument.find_all("td")[1].string).replace(tzinfo=timezone.utc)
      add_argument(feed, argument_id, argument_number, argument_title, argument_date, docket_number)

if __name__ == "__main__":
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
