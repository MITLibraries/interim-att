# Dropbox API and SDK information

There was some confusion around the Dropbox API, the correct scoped permissions for the Dropbox "app", and the Dropbox Python SDK.

## Requirement

To access the Dropbox API, it is a **requirement** that a Dropbox App is created in the Dropbox App Console: [https://www.dropbox.com/developers/apps](https://www.dropbox.com/developers/apps). The app can remain in **Development** status -- there is no need to go through the process to apply for Production status. Sadly, it is only possible to have one owner/manager of the app. Other users can use the key/secret from the app to authenticate.

## Rule #1: Scope App Correctly

Even though the Python script will need to access files and file metadata on a "Team Folder" the only scoped access that the app needs is the regular `files.content_read` and the `file_requests.read` under the **User Scopes** heading in the Permissions tab for the app in the App Console. The permissions in the **Team Scopes** section are only for full Dropbox Team Admins (in our case, that is members of IS&T that support our Dropbox contract).

## Rule #2: During OAuth, set path correctly

Use the regular OAuth workflows provided by the Dropbox Python SDK. But, when returning the `dropbox.Dropbox()` object, you must return that object using the `with_path_root()` set correctly. By default, the OAuth object returned by `dropbox.Dropbox()` is only able to see the user folder. By returning `dropbox.Dropbox().with_path_root()`, you can set the root path differently and open up access to the Team Folder also. This is explained (albeit, not very well) in the **DBX Team Files Guide** linked below.

## Code snippets used in testing

This was useful to verify where the app was actually looking for files:

```python
## For testing whether we can access the Dropbox Team Folder
dbx = dropbox_oauth_pkce()
print(dbx.users_get_current_account())
result = dbx.files_list_folder(path="/ArchivesTransfer/SampleFolder1", recursive=True)
for entry in result.entries:
    print(entry)
```

## Useful links

* [Dropbox](https://dropbox.com)
* [Dropbox App Console for Developers](https://dropbox.com/developers/apps)
* [merge.dev: How to GET folders from the Dropbox API in Python](https://www.merge.dev/blog/dropbox-api-get-folders)
* [dropboxforum.com: file list from shared folder dropbox rest api python](https://www.dropboxforum.com/discussions/101000014/file-list-from-shared-folder-dropbox-rest-api-python/512455)
* [dropboxforum.com: Forced to make all users Team Admins? "You must be a team administrator to authorize this app"](https://www.dropboxforum.com/discussions/101000014/forced-to-make-all-users-team-admins-you-must-be-a-team-administrator-to-authori/486473)
* [dropboxforum.com: Get all shared links for a file](https://www.dropboxforum.com/discussions/101000014/get-all-shared-links-for-a-file/677953)
* [developers.dropbox.com: DBX Team Files Guide](https://developers.dropbox.com/dbx-team-files-guide#namespaces)
* [dropboxforum.com: Problem with listing team folder with python SDK: Error in call to API function "files/list_folder](https://www.dropboxforum.com/discussions/101000042/problem-with-listing-team-folder-with-python-sdk-error-in-call-to-api-function-f/611359)
* [developers.dropbox.com: OAuth Guide](https://developers.dropbox.com/oauth-guide#implementing-oauth)
* [github: Dropbox SDK Example](https://github.com/dropbox/dropbox-sdk-python/blob/main/example/back-up-and-restore/backup-and-restore-example.py)
