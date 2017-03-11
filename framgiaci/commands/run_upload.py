import sys
import os
import xml.etree.ElementTree as ET
import zipfile

from cleo import Command

from framgiaci.common import print_header, build_params, read_results, call_api


class RunUploadCommand(Command):
    """
    Running build and upload reports command

    upload
    """

    ALL_REPORTS = [
        'checkstyle.xml', 'pmd.xml', 'android_lint.xml', # Android
        'rubocop-output-checkstyle.xml', 'reek-output.xml', # Ruby
        'pdepend.xml', 'phpcpd.xml', 'phpcs.xml', 'phpmd.xml', # PHP
        'eslint.xml', # JS
        'swift-lint.xml', # Swift
    ]


    def handle(self):
        print_header('Build and upload reports')
        base_api_url = self.app.ci_reports['url'] + '/api/reports'
        # base_api_url = 'localhost:12345'
        params = build_params()
        params['project_type'] = self.app.ci_reports['project_type'] if 'project_type' in self.app.ci_reports else None
        params['test_result'] = read_results(self.app.temp_file_name)

        self.build_zip_file(params)

        call_api(base_api_url, True, params, [], [('report_file', 'bundle_reports.zip')])


    def build_zip_file(self, params, basedir='.framgia-ci-reports'):
        files_list = []
        bundle_zip = zipfile.ZipFile('bundle_reports.zip', 'w')

        for root, dirs, files in os.walk(basedir):
            for file in files:
                if file in file in self.ALL_REPORTS:
                    xml_report_file = os.path.join(basedir, file)
                    files_list += self.rebuild_and_extract_xml(xml_report_file, params)
                bundle_zip.write(os.path.join(basedir, file), os.path.join('reports', file), zipfile.ZIP_DEFLATED)

        files_list = list(set(files_list))

        for file in files_list:
            full_path = os.path.join(os.getcwd(), file)
            try:
                bundle_zip.write(full_path, os.path.join('src', file), zipfile.ZIP_DEFLATED)
            except Exception as e:
                print('[-]', e)

        bundle_zip.close()


    def get_base_root(self, root, file_name):
        if root.tag in ['checkstyle', 'pmd']:
            return root
        if 'pdepend.xml' in file_name:
            return [c for c in root if c.tag == 'files'][0]
        if 'phpcpd.xml' in file_name:
            return [c for c in root if c.tag == 'duplication'][0]
        if 'android_lint.xml' in file_name:
            return [location for issue in root for location in issue]


    def rebuild_and_extract_xml(self, xml_file, params):
        try:
            tree = ET.parse(xml_file)
        except Exception:
            print('[-] Bad XML:', xml_file)
            return []
        root = tree.getroot()
        files = []
        cwd = os.getcwd()
        updated = False
        base_root = self.get_base_root(root, xml_file)
        for child in base_root:
            if child.attrib.get('name', None):
                tag = 'name'
            elif child.attrib.get('path', None):
                tag = 'path'
            elif child.attrib.get('file', None):
                tag = 'file'

            fixed_path = child.attrib[tag]
            # iOS work around
            if 'swift-lint.xml' in xml_file:
                repo = params['repo']['name']
                fixed_path = fixed_path.split(repo)[-1][1:]
                updated = True
            elif os.path.isabs(fixed_path):
                fixed_path = os.path.relpath(fixed_path, cwd)
                child.set(tag, fixed_path)
                updated = True
            files.append(fixed_path)

        if updated:
            tree.write(xml_file)

        return files