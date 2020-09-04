#!/usr/bin/python

# Copyright: (c) 2019, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ap_exchange_asset

short_description: Manage an Asset on Exchange

version_added: "2.8"

description:
    - "This module supports upload, modify and delete assets on Exchange"

options:
    name:
        description:
            - Exchange asset name.
    state:
        description:
            - Assert the state of the asset. Use C(present) to create an asset undeprecated, C(deprecated) toi deprecate it and C(absent) to delete it.
        required: true
        choices: [ "present", "deprecated", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    organization:
        description:
            - Anypoint Platform Organization Name to work on
        required: true
    organization_id:
        description:
            - Anypoint Platform Organization Id to work on. Required for C(present) and C(deprecated) states
        required: false
    type:
        description:
            - The asset type
            - Mule 3 connectors supported (type "connector")
            - Mule 4 connectors supported (type "extension")
            - Mule 4 policies supported (type "policy")
        required: true
        choices: [ "custom", "oas", "wsdl", "example", "template", "extension", "connector", "policy" ]
    group_id:
        description:
            - The asset groupId
        required: true
    asset_id:
        description:
            - The asset assetId
        required: true
    asset_version:
        description:
            - The asset version
        required: false
        default: 1.0.0
    api_version:
        description:
            - The api version
        required: false
        default: 1.0
    main_file:
        description:
            - Main file of the API asset
            - Use it only for asset types "custom", "oas" and "wsdl"
        type: path
        required: false
    file_path:
        description:
            - Path to the asset file. Required for C(present)
            - If points to a ZIP/JAR archive file, that archive must include an C(exchange.json) file describing the asset
        type: path
        required: false
    tags:
        description:
            - A list of tags for the asset
        type: list
        required: false
    description:
        description:
            - A description for the asset
        required: false
    icon:
        description:
            - Path to the asset icon file
            - Supported extensions are svg, png, jpg, jpeg
        type: path
        required: false
    maven:
        description:
            - Provides maven configuration if it is necessary
            - Used for C(present) for asset types "example" and "template" for maven build goal
            - Not required if you already specified C(file_path) option
        suboptions:
            sources:
                description:
                    - Directory with the sources of a mule application
                    - In this directory must exists a pom.xml file
                    - Required for C(present) for asset types "example" and "template"
                type: path
                required: false
            settings:
                description:
                    - Global settings file that the module will use to deploy the asset
                    - The module uses a dynamically-created user settings by default
                    - If this is specified, then the content will be merged with the user settings by maven
                    - This is particulary usefull to resolve external dependencies
                type: path
                required: false
            pom:
                description:
                    - Custom pom.xml file that the module should use to deploy the assets
                    - If this is not specified, it will be used the one specified in "sources"
                    - If you set this option, maven will be forced to use it instead of the project one
                type: path
                required: false
            arguments:
                description:
                    - Comma separated list of arguments to pass to maven
                    - Each element should be specified as "key=value"
                    - Used as "mvn ... -Dkey1=value1 -Dkey2=value2... "
                type: list
                required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
   - mvn
'''

EXAMPLES = '''
# Example of uploading an exchange
- name: Upload Exchange Asset
  ap_exchange_asset:
    name: 'My Asset'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
    main_file: '/tmp/custom.csv'

# Example of deprecating an exchange asset
- name: Deprecate Exchange Asset
  ap_exchange_asset:
    name: 'My Asset'
    state: 'deprecated'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'

# Example of deleting an exchange asset
- name: Delete Exchange Asset
  ap_exchange_asset:
    name: 'home'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
'''

RETURN = '''
msg:
    description: Operation result
    type: str
    returned: always
'''

import json
import importlib
import os
import xml.etree.ElementTree as ET
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_exchange_common


def get_maven_path(module):
    return module.get_bin_path('mvn', True, ['/usr/local/bin'])


def execute_maven(module, cmd):
    final_cmd = get_maven_path(module)
    final_cmd += ' ' + cmd
    result = module.run_command(final_cmd)
    if result[0] != 0:
        module.fail_json(msg='[execute_maven] ' + result[1])

    return result[1]


def get_tmp_dir():
    return '/tmp'


def look_asset_on_exchange(module):
    return_value = None
    # Query exchange using the Graph API
    output = ap_exchange_common.look_exchange_asset_with_graphql(module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    if (output.get('errors')):
        if (output['errors'][0].get('status') != 404):
            module.fail_json(msg='[look_asset_on_exchange] Error looking for asset on exchange: ' + output['errors'][0]['message'])
    else:
        # check if the asset exists
        item = output['data']['assets'][0]
        if (module.params['asset_id'] == item['assetId']
                and module.params['group_id'] == item['groupId']
                and module.params['asset_version'] == item['version']
                and module.params['type'] == item['type']):
            return_value = item['assetId']

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        exists=False,
        exchange_must_update=False,
        exchange_must_update_name=False,
        exchange_must_update_icon=False,
        exchange_must_update_description=False,
        exchange_must_update_tags=False,
        deprecated=False
    )

    asset_id = look_asset_on_exchange(module)
    if (asset_id is not None):
        return_value['exists'] = True

    if (module.params['state'] == "present") or (module.params['state'] == "deprecated"):
        if (return_value['exists'] is True):
            result = ap_exchange_common.analyze_asset(
                module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'],
                module.params.get('name'), module.params.get('description'), module.params.get('icon'), module.params.get('tags'))
            return_value['exchange_must_update'] = result['must_update']
            return_value['exchange_must_update_name'] = result['must_update_name']
            return_value['exchange_must_update_icon'] = result['must_update_icon']
            return_value['exchange_must_update_description'] = result['must_update_description']
            return_value['exchange_must_update_tags'] = result['must_update_tags']
            return_value['deprecated'] = result['deprecated']
            if (module.params['state'] == "present"):
                return_value['do_nothing'] = (return_value['exchange_must_update'] is False and return_value['deprecated'] is False)
            elif (module.params['state'] == "deprecated"):
                return_value['do_nothing'] = (return_value['deprecated'] is True)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = not return_value['exists']
    return return_value


def get_settings_xml_path(module):
    return get_tmp_dir() + '/' + module.params['group_id'] + '_' + module.params['asset_id'] + '_settings.xml'


def create_settings_xml(module):
    xml_content = ''
    xml_content += r'<?xml version="1.0" encoding="UTF-8"?>' + '\n'
    xml_content += r'<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"' + '\n'
    xml_content += r'          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' + '\n'
    xml_content += r'          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">' + '\n'
    xml_content += r'    <servers>' + '\n'
    xml_content += r'        <server>' + '\n'
    xml_content += r'            <id>Repository</id>' + '\n'
    xml_content += r'            <username>~~~Token~~~</username>' + '\n'
    xml_content += r'            <password>' + module.params['bearer'] + r'</password>' + '\n'
    xml_content += r'        </server>' + '\n'
    xml_content += r'        <server>' + '\n'
    xml_content += r'            <id>anypoint-exchange</id>' + '\n'
    xml_content += r'            <username>~~~Token~~~</username>' + '\n'
    xml_content += r'            <password>' + module.params['bearer'] + r'</password>' + '\n'
    xml_content += r'        </server>' + '\n'
    xml_content += r'        <server>' + '\n'
    xml_content += r'            <id>anypoint-exchange-v2</id>' + '\n'
    xml_content += r'            <username>~~~Token~~~</username>' + '\n'
    xml_content += r'            <password>' + module.params['bearer'] + r'</password>' + '\n'
    xml_content += r'        </server>' + '\n'
    xml_content += r'    </servers>' + '\n'
    xml_content += r'</settings>' + '\n'
    # create the settings file
    try:
        f = open(get_settings_xml_path(module), "w")
        f.write(xml_content)
        f.close()
    except Exception as e:
        module.fail_json(msg=('[create_settings_xml] Can not create settings.xml file dynamically [' + str(e) + ']'))

    return True


def get_distribution_repository_url(module):
    return_value = 'https://maven.'
    return_value += module.params['host']
    return_value += '/api/v1/organizations/'
    return_value += module.params['group_id']
    return_value += '/maven'

    return return_value


def modify_pom_file(module, source_pom):
    ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')
    tree = ET.parse(source_pom)
    root = tree.getroot()
    version_elem = root.find('{http://maven.apache.org/POM/4.0.0}version')
    actifact_id_elem = root.find('{http://maven.apache.org/POM/4.0.0}artifactId')
    group_id_elem = root.find('{http://maven.apache.org/POM/4.0.0}groupId')
    name_elem = root.find('{http://maven.apache.org/POM/4.0.0}name')
    build_elem = root.find('{http://maven.apache.org/POM/4.0.0}build')
    dependencies_elem = root.find('{http://maven.apache.org/POM/4.0.0}dependencies')
    # modify with supplied values
    version_elem.text = module.params['asset_version']
    actifact_id_elem.text = module.params['asset_id']
    group_id_elem.text = module.params['group_id']
    name_elem.text = module.params['name']
    # update classifier
    plugins_elem = build_elem.find('{http://maven.apache.org/POM/4.0.0}plugins')
    for plugin in plugins_elem.findall('{http://maven.apache.org/POM/4.0.0}plugin'):
        if (plugin.find('{http://maven.apache.org/POM/4.0.0}artifactId').text == 'mule-maven-plugin'):
            classifier_elem = plugin.find('{http://maven.apache.org/POM/4.0.0}configuration').find('{http://maven.apache.org/POM/4.0.0}classifier')
            if (module.params['type'] == 'example'):
                tmp_classifier = 'mule-application-example'
            elif (module.params['type'] == 'template'):
                tmp_classifier = 'mule-application-template'
            classifier_elem.text = tmp_classifier
    # replace '${bg_id}' with group_id, only used on automation use cases
    for dependency in dependencies_elem.findall('{http://maven.apache.org/POM/4.0.0}dependency'):
        tmp_elem = dependency.find('{http://maven.apache.org/POM/4.0.0}groupId')
        if (tmp_elem.text == r'${bg_id}'):
            tmp_elem.text = module.params['group_id']
    # finally write out content to the pom.xml file
    tree.write(source_pom)


def upload_exchange_asset(module, context, cmd_base, asset_identifier):
    return_value = 'Asset uploaded'
    if ((module.params['type'] == "custom")
            or (module.params['type'] == "oas")
            or (module.params['type'] == "wsdl")):
        upload_cmd = cmd_base
        upload_cmd += ' upload'
        upload_cmd += ' --name "' + module.params['name'] + '"'
        if (module.params['main_file'] is not None):
            upload_cmd += ' --mainFile "' + module.params['main_file'] + '"'
        upload_cmd += ' --classifier "' + module.params['type'] + '"'
        upload_cmd += ' "' + asset_identifier + '"'
        if (module.params['file_path'] is not None):
            upload_cmd += ' "' + module.params['file_path'] + '"'
        ap_common.execute_anypoint_cli('[upload_exchange_asset]', module, upload_cmd)
    elif ((module.params['type'] == "example")
            or (module.params['type'] == "template")
            or (module.params['type'] == "connector")
            or (module.params['type'] == "extension")
            or (module.params['type'] == "policy")):
        deploy_cmd = ''
        if ((module.params['type'] == 'example' or module.params['type'] == 'template')
                and (module.params['file_path'] is None)):
            if (module.params['maven']['sources'] is not None):
                # need to build the asset from the sources
                deploy_cmd += '-U -B clean deploy -DskipTests -DattachMuleSources=true'
                # process global settings file
                if (module.params['maven'] is not None) and (module.params['maven'].get('settings') is not None):
                    deploy_cmd += ' -gs "' + module.params['maven'].get('settings') + '"'
                # process user settings file
                create_settings_xml(module)
                deploy_cmd += ' -s "' + get_settings_xml_path(module) + '"'
                # process alternate pom file
                source_pom = ''
                if (module.params['maven'] is not None) and (module.params['maven'].get('pom')):
                    source_pom = module.params['maven'].get('pom')
                else:
                    source_pom = module.params['maven']['sources'] + '/pom.xml'
                # update group id, artifact id and version on the selected pom.xml
                modify_pom_file(module, source_pom)
                deploy_cmd += ' -f "' + source_pom + '"'
                # add specified variables
                if (module.params['maven'] is not None and module.params['maven'].get('arguments')):
                    user_args = ''
                    user_args += " -D".join(module.params['maven'].get('arguments'))
                    deploy_cmd += user_args
                # set alternative deployment repository
                deployment_repository = get_distribution_repository_url(module)
                deploy_cmd += ' -DaltDeploymentRepository="' + 'Repository::default::' + deployment_repository + '"'
                # finally execute the maven command
                execute_maven(module, deploy_cmd)
            else:
                module.fail_json(
                    msg='[upload_exchange_asset] asset type "template" or "example" requires either a project directory'
                        'to build it or a file to just upload it'
                )
        else:
            # just upload provided file
            deploy_cmd += 'deploy:deploy-file'
            # process user settings file
            create_settings_xml(module)
            deploy_cmd += ' -s "' + get_settings_xml_path(module) + '"'
            # set the required pom attributes
            deploy_cmd += ' -Dfile="' + module.params['file_path'] + '"'
            deploy_cmd += ' -DrepositoryId=Repository'
            deploy_cmd += ' -DartifactId=' + module.params['asset_id']
            deploy_cmd += ' -DgroupId=' + module.params['group_id']
            deploy_cmd += ' -Dversion=' + module.params['asset_version']
            # set classifier: studio-plugin for Mule 3 connectors or mule-plugin for Mule 4 connectors or mule-policy for mule 4 policies
            file_extension = os.path.splitext(module.params['file_path'])[1]
            if ((module.params['type'] == 'connector') and (file_extension == '.zip')):
                deploy_cmd += ' -Dclassifier=studio-plugin'
            elif ((module.params['type'] == 'extension') and (file_extension == '.jar')):
                deploy_cmd += ' -Dclassifier=mule-plugin'
            elif ((module.params['type'] == 'policy') and (file_extension == '.jar')):
                deploy_cmd += ' -Dclassifier=mule-policy'
            elif ((module.params['type'] == 'example') and (file_extension == '.jar')):
                deploy_cmd += ' -Dclassifier=mule-application-example'
            elif ((module.params['type'] == 'template') and (file_extension == '.jar')):
                deploy_cmd += ' -Dclassifier=mule-application-template'
            else:
                module.fail_json(
                    msg='[upload_exchange_asset] invalid file extension for ' + module.params['type'] + ' asset type '
                        '(only supported .zip for mule 3 and .jar for mule 4)'
                )
            deploy_cmd += ' -Durl=' + get_distribution_repository_url(module)
            # finally execute the maven command
            execute_maven(module, deploy_cmd)
            # set the asset name: this is required just for extension asset type
            ap_exchange_common.set_asset_name(
                module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'], module.params['name']
            )

    # update other fields if it is necessary
    ap_exchange_common.modify_exchange_asset(
        module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'],
        context, module.params['name'], module.params['description'], module.params['icon'], module.params['tags']
    )

    return return_value


def run_module():
    # define maven spec
    maven_spec = dict(
        sources=dict(type='path', required=False, default=None),
        settings=dict(type='path', required=False, default=None),
        pom=dict(type='path', required=False, default=None),
        arguments=dict(type='list', required=False, default=[])
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "deprecated", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=True),
        type=dict(type='str', required=True, choices=['custom', 'oas', 'wsdl', 'example', 'template', 'extension', 'connector', 'policy']),
        group_id=dict(type='str', required=True),
        asset_id=dict(type='str', required=True),
        asset_version=dict(type='str', required=False, default="1.0.0"),
        api_version=dict(type='str', required=False, default="1.0"),
        main_file=dict(type='path', required=False, default=None),
        file_path=dict(type='path', required=False, default=None),
        tags=dict(type='list', required=False, default=[]),
        description=dict(type='str', required=False),
        icon=dict(type='path', required=False, default=None),
        maven=dict(type='dict', options=maven_spec)
    )
    result = dict(
        changed=False,
        msg='No action taken'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (ap_common.get_anypointcli_path(module) is None):
        module.fail_json(msg="[run_module] anypoint-cli binary not present on host")

    if (get_maven_path(module) is None):
        module.fail_json(msg="[run_module] maven binary not present on host")

    if module.check_mode:
        module.exit_json(**result)

    cmd_base = ap_common.get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd_base += ' --host="' + module.params['host'] + '"'
    cmd_base += ' --organization="' + module.params['organization'] + '"'
    cmd_base += ' exchange asset'

    # convert empty strings to None if it is necessary
    # this could be redundant, but can help you with automatically-generated playbooks
    if (module.params['main_file'] == ''):
        module.params['main_file'] = None
    if (module.params['file_path'] == ''):
        module.params['file_path'] = None
    if (module.params['icon'] == ''):
        module.params['icon'] = None
    if (module.params['description'] == ''):
        module.params['description'] = None
    if (module.params['maven'] is not None) and (module.params['maven'].get('sources') == ''):
        module.params['maven']['sources'] = None

    # validate required parameters
    if ((module.params['state'] == 'present')
            and ((module.params['type'] == 'example') or (module.params['type'] == 'template'))):
        if ((module.params['maven'] is None) or (module.params['maven'].get('project_dir') is not None)):
            module.fail_json(msg='asset type template or example requires a project directory to build it')

    if (module.params['state'] == 'present'):
        if ((module.params['type'] == 'oas')
                or (module.params['type'] == 'wsdl')
                or (module.params['type'] == 'connector')
                or (module.params['type'] == 'extension')
                or (module.params['type'] == 'policy')):
            if (module.params['file_path'] is None):
                module.fail_json(msg='[run_module] asset type oas, wsdl, connector, extension or policy requires a file path to upload it')

    # exit if I need to do nothing, so check if environment exists
    context = get_context(module, cmd_base)
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    asset_identifier = ap_exchange_common.get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    if (module.params['state'] == 'present'):
        # if it doesn't exists then upload
        if (context['exists'] is False):
            output = upload_exchange_asset(module, context, cmd_base, asset_identifier)
        else:
            # if it exists and it is deprecated, then undeprecate it
            if (context['deprecated'] is True):
                undeprecate_cmd = cmd_base
                undeprecate_cmd += ' undeprecate "' + asset_identifier + '"'
                output = ap_common.execute_anypoint_cli('[run_module]', module, undeprecate_cmd)
            # if it exists and must change then modify
            if (context['exchange_must_update'] is True):
                output = ap_exchange_common.modify_exchange_asset(
                    module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'], context,
                    module.params['name'], module.params['description'], module.params['icon'], module.params['tags']
                )
    elif (module.params['state'] == 'deprecated'):
        if (context['exists'] is False):
            output = upload_exchange_asset(module, context, cmd_base, asset_identifier)
        # if it exists and must change then modify
        if (context['exchange_must_update'] is True):
            output = ap_exchange_common.modify_exchange_asset(
                module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'],
                context, module.params['name'], module.params['description'], module.params['icon'], module.params['tags']
            )
        # finally just deprecate the asset
        deprecate_cmd = cmd_base
        deprecate_cmd += ' deprecate "' + asset_identifier + '"'
        output = ap_common.execute_anypoint_cli('[run_module]', module, deprecate_cmd)
    elif (module.params['state'] == 'absent'):
        output = ap_exchange_common.delete_exchange_asset(module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'])

    result['msg'] = output.replace('\n', '')
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
