from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.datafactory.models import *
from datetime import datetime, timedelta
import time


def print_item(group):
    """Print an Azure object instance."""
    print("\tName: {}".format(group.name))
    print("\tId: {}".format(group.id))
    if hasattr(group, 'location'):
        print("\tLocation: {}".format(group.location))
    if hasattr(group, 'tags'):
        print("\tTags: {}".format(group.tags))
    if hasattr(group, 'properties'):
        print_properties(group.properties)
    print("\n")


def print_properties(props):
    """Print a ResourceGroup properties instance."""
    if props and hasattr(props, 'provisioning_state') and props.provisioning_state:
        print("\tProperties:")
        print("\t\tProvisioning State: {}".format(props.provisioning_state))
    print("\n")


def print_activity_run_details(activity_run):
    """Print activity run details."""
    print("\n\tActivity run details\n")
    print("\tActivity run status: {}".format(activity_run.status))
    if activity_run.status == 'Succeeded':
        print("\tNumber of bytes read: {}".format(
            activity_run.output['dataRead']))
        print("\tNumber of bytes written: {}".format(
            activity_run.output['dataWritten']))
        print("\tCopy duration: {}".format(
            activity_run.output['copyDuration']))
    else:
        print("\tErrors: {}".format(activity_run.error['message']))


def main():

    # Azure subscription ID
    subscription_id = 'a1b8793b-91d4-42e0-9e7a-f55af294f275'

    # This program creates this resource group. If it's an existing resource group, comment out the code that creates the resource group
    rg_name = 'newcopyBlobToSqlRg'

    # The data factory name. It must be globally unique.
    df_name = 'newcopyBlobToSqlDf'

    # Specify your Active Directory client ID, client secret, and tenant ID
    credentials = ServicePrincipalCredentials(
        client_id='31fe72da-bb34-4243-a365-288a003d57e9', secret='702f129a-cc5e-4b03-9a5d-362ee0a6d4e3', tenant='c80b7188-f79b-48e5-8008-f9402f981907')
    resource_client = ResourceManagementClient(credentials, subscription_id)
    adf_client = DataFactoryManagementClient(credentials, subscription_id)

    rg_params = {'location': 'eastus'}
    df_params = {'location': 'eastus'}

    # # create the resource group
    # # comment out if the resource group already exits
    # resource_client.resource_groups.create_or_update(rg_name, rg_params)

    # # Create a data factory
    # df_resource = Factory(location='eastus')
    # df = adf_client.factories.create_or_update(rg_name, df_name, df_resource)
    # print_item(df)
    # while df.provisioning_state != 'Succeeded':
    #     df = adf_client.factories.get(rg_name, df_name)
    #     time.sleep(1)

    # Create an Azure Storage linked service
    ls_name = 'storageLinkedService'

    # Specify the name and key of your Azure Storage account
    storage_string = SecureString(
        value='DefaultEndpointsProtocol=https;AccountName=copyblobtosqlstorage;AccountKey=WlOWgmkCT9a8FB2phDVEgZhCfsrP1p/ZT8pA9Rg63iHyXB2+cZcQmHb8h0g+d3c6WoLa1aDef4fCJ4szkj0ipg==')

    ls_azure_storage = AzureStorageLinkedService(
        connection_string=storage_string)
    ls = adf_client.linked_services.create_or_update(
        rg_name, df_name, ls_name, ls_azure_storage)
    print_item(ls)

    # Create an Azure blob dataset (input)
    ds_name = 'salary_details_in'
    ds_ls = LinkedServiceReference(reference_name=ls_name)
    blob_path = 'data-streaming-sync/csv/salaryDetails/'
    # blob_filename = 'input.txt'
    ds_azure_blob = AzureBlobDataset(
        linked_service_name=ds_ls, folder_path=blob_path)
    ds = adf_client.datasets.create_or_update(
        rg_name, df_name, ds_name, ds_azure_blob)
    print_item(ds)


    # Create an Azure Sql database linked service
    ls_sql_name = 'sqlDatabaseLinkedService'
    rg_sql_name='cloud-shell-storage-southeastasia'
    df_sql_name='datafactoryBlobToSql'

    storage_string='Server = tcp:datafactorysync-kpi-server.database.windows.net, 1433;'+'Database=datafactorysync_kpi'
    ls_azure_sql_storage = AzureSqlDatabaseLinkedService(connection_string =storage_string,password = '*******',service_principal_id = '31fe72da-bb34-4243-a365-288a003d57e9',type ='AzureSqlDatabase')
    ls = adf_client.linked_services.create_or_update(rg_sql_name, df_sql_name, ls_sql_name, ls_azure_sql_storage)
    print_item(ls)

    # Create an Azure sql database (output)
    dsOut_name = 'salary_details_out'
    ds_sql_ls = LinkedServiceReference(reference_name=ls_sql_name)
    ds_sql_table_name='dbo.Salary_Details'
    ds = adf_client.datasets.create_or_update(
        rg_sql_name, df_sql_name, ds_sql_ls, ds_sql_table_name)
    print_item(ds)

    # Create a copy activity
    act_name = 'copyBlobtoSql'
    blob_source = BlobSource()
    sql_sink = SqlSink()
    dsin_ref = DatasetReference(reference_name=ds_name)
    dsOut_ref = DatasetReference(reference_name=dsOut_name)
    copy_activity = CopyActivity(name=act_name, inputs=[dsin_ref], outputs=[
                                 dsOut_ref], source=blob_source, sink=sql_sink)

    # Create a pipeline with the copy activity
    p_name = 'copyPipeline'
    params_for_pipeline = {}
    p_obj = PipelineResource(
        activities=[copy_activity], parameters=params_for_pipeline)
    p = adf_client.pipelines.create_or_update(rg_name, df_name, p_name, p_obj)
    print_item(p)

    # Create a pipeline run
    run_response = adf_client.pipelines.create_run(rg_name, df_name, p_name, parameters={})

    # Monitor the pipeline run
    time.sleep(30)
    pipeline_run = adf_client.pipeline_runs.get(
        rg_name, df_name, run_response.run_id)
    print("\n\tPipeline run status: {}".format(pipeline_run.status))
    filter_params = RunFilterParameters(
        last_updated_after=datetime.now() - timedelta(1), last_updated_before=datetime.now() + timedelta(1))
    query_response = adf_client.activity_runs.query_by_pipeline_run(
        rg_name, df_name, pipeline_run.run_id, filter_params)
    print_activity_run_details(query_response.value[0])
    #

# Start the main method
main()