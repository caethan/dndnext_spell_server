import json
import os
from urllib import unquote_plus
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import TCPServer
from StringIO import StringIO

SERVER_ADDRESS = ''
SERVER_PORT = 8080

# Default to the SRD files but if other files are available, read those in instead
SPELL_DATABASE_FILES = ['data/SRD_spell_card.json']
other_files = [fn for fn in os.listdir('data') if fn.endswith('.json') and not fn.startswith('SRD_spell_card')]
if other_files:
    SPELL_DATABASE_FILES = [os.path.join('data', fn) for fn in other_files]
SPELLS_TEMPLATE = 'spell_server.html'


def SpellDatabase(object):
    def __init__(self, source_files):
        """Load in all the input files - just hold everything in memory."""
        self.database = {}
        for filename in source_files:
            self.load_file(filename)

    def load_file(self, filename):
        pass

    def parse_spell(self, spell_name):
        if spell_name not in self.database:
            return None
        spell = self.database[spell_name]
        title = spell['title']
        tags = spell['tags']
        properties = [line[11:] for line in spell['contents'] if line.startswith('property')]
        subtitle = [line[11:] for line in spell['contents'] if line.startswith('subtitle')]
        subtitle = subtitle[0] if subtitle else ''
        text_lines = [line[7:] for line in spell['contents'] if line.startswith('text')]
        return title, subtitle, text_lines, tags, properties


class DndSpellsWeb(SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        """Load in spell data and the html template from files, then initialize the HTTP server."""
        self.json_data = []
        for spell_fn in SPELL_DATABASE_FILES:
            with open(spell_fn, 'r') as infile:
                self.json_data.extend(json.load(infile))
        with open(SPELLS_TEMPLATE) as template_file:
            self.template_data = template_file.read()
        SimpleHTTPRequestHandler.__init__(self, request, client_address, server)

    def send_head(self):
        body = None

        if self.path == '/':
            body = self.parse_index()
        else:
            try:
                spell_end = self.path.index('/', 1)
            except:
                return SimpleHTTPRequestHandler.send_head(self)
            if spell_end > 1:
                spell_name = unquote_plus(self.path[1:spell_end])
                for spell in self.json_data:
                    if spell['title'] == spell_name:
                        body = self.parse_spell(spell)
                    elif spell['title'].lower() == spell_name:
                        body = self.parse_spell(spell)
                if body is None:
                    self.send_error(404, "Spell '%s' not found." % spell_name)
                    return None

        # Send body or default handler
        if body:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return StringIO(body)
        else:
            return SimpleHTTPRequestHandler.send_head(self)

    def parse_index(self):
        response = self.template_data
        cut_from = response.index(u"<main>")
        cut_to = response.index(u"</main>")

        spells = sorted([spell for spell in self.json_data], key=lambda x: x['title'])

        center = """
        <table>
        <tr>
        <th>Title</th>
        <th>Level</th>
        <th>School</th>
        <th>Components</th>
        <th>Classes</th>
        <th>Sources</th>
        <th>Other</th>
        </tr>
        {}
        </table>
        """.format('\n'.join(self.spell_to_table_row(spell) for spell in spells))

        return response[0:cut_from - 1] + center + response[cut_to + 8:]

    def spell_to_table_row(self, spell):
        title = spell['title']
        tags = spell['tags']

        valid_levels = ['cantrip', '1st-level', '2nd-level', '3rd-level', '4th-level', '5th-level', '6th-level',
                        '7th-level', '8th-level', '9th-level']
        valid_classes = ['bard', 'sorcerer', 'wizard', 'druid', 'cleric', 'warlock', 'ranger', 'paladin']
        valid_sources = ['PHB', 'SCAG', 'XGE']
        valid_schools = ['enchantment', 'abjuration', 'illusion', 'transmutation',
                         'necromancy', 'evocation', 'divination', 'conjuration']
        valid_components = ['verbal', 'somatic', 'material']

        spell_level = ''
        spell_classes = []
        spell_sources = []
        spell_school = ''
        spell_components = []
        other_tags = []

        for tag in tags:
            if tag in valid_levels:
                if tag.endswith('-level'):
                    spell_level = tag[:-6]
                else:
                    spell_level = tag
            elif tag in valid_schools:
                spell_school = tag
            elif tag in valid_classes:
                spell_classes.append(tag)
            elif tag in valid_sources:
                spell_sources.append(tag)
            elif tag in valid_components:
                spell_components.append(tag[0].upper())
            else:
                other_tags.append(tag)

        spell_classes = ', '.join(spell_classes)
        spell_sources = ', '.join(spell_sources)
        spell_components = ''.join(spell_components)
        other_tags = ', '.join(other_tags)

        return """
        <tr>
        <td><a href="./{title}/">{title}</a></td>
        <td>{spell_level}</td>
        <td>{spell_school}</td>
        <td>{spell_components}</td>
        <td>{spell_classes}</td>
        <td>{spell_sources}</td>
        <td>{other_tags}</td>
        </tr>
        """.format(**locals())

    def parse_spell(self, spell):
        spell_title = u''
        spell_subtitle = u''
        spell_properties = []
        spell_p = []
        for field in spell:
            if field == "title":
                spell_title = spell[field]
            elif field == "contents":
                for content in spell[field]:
                    if content.startswith('subtitle'):
                        spell_subtitle = content[11:]
                    if content.startswith("property"):
                        spell_properties.append(content[11:])
                    if content.startswith("fill"):
                        brs = int(content[7:])
                        for i in range(brs):
                            spell_p.append("")
                    if content.startswith("text"):
                        spell_p.append(content[7:])
                    if content.startswith("bullet"):
                        spell_p.append('&bull;{}'.format(content[9:]))

        spell_content = u''

        if spell_title:
            spell_content += u"<header><h1>" + spell_title + u"</h1>"
            if spell_subtitle:
                spell_content += u"<p>" + spell_subtitle + u"</p>"
            spell_content += u"</header>"

        if spell_properties:
            spell_content += u"<ul>"
            for prop in spell_properties:
                spell_content += u"<li>" + prop + u"</li>"
            spell_content += u"</ul>"

        if spell_p:
            for p in spell_p:
                spell_content += u"<p>" + (u"&nbsp;" if p == u"" else p) + u"</p>"

        response = self.template_data
        cut_from = response.index(u"<main>")
        cut_to = response.index(u"</main>")
        return response[0:cut_from + 6] + spell_content + response[cut_to:]


def main():
    """Set up and run the server"""
    server_address = (SERVER_ADDRESS, SERVER_PORT)
    httpd = TCPServer(server_address, DndSpellsWeb)
    server_name = 'localhost' if server_address[0] == '' else server_address[0]
    print "http://%s:%s" % (server_name, server_address[1])
    httpd.serve_forever()


if __name__ == "__main__":
    main()
