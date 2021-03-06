# Initial setup

Prepare the computer:

    ansible-playbook -i hosts server_setup.yml

Install the software:

    ansible-playbook -i hosts server_install.yml

Link the nginx and supervisor configurations:

    ln -sf /export/sites/biostar-engine/conf/site/site_nginx.conf /etc/nginx/sites-enabled/
    ln -sf /export/sites/biostar-engine/conf/site/site_supervisor.conf /etc/supervisor/conf.d/ 
        
Initialize the certificates

    sudo certbot --nginx

You should test your configuration at:

* https://www.ssllabs.com/ssltest/analyze.html?d=bioinformatics.recipes
* https://www.ssllabs.com/ssltest/analyze.html?d=data.bioinformatics.recipes
* https://www.ssllabs.com/ssltest/analyze.html?d=www.bioinformatics.recipes

## Deployment

The following will pull the new content and restart the servers:

    ansible-playbook -i hosts server_deploy.yml --ask-become-pass


To restart servers alone:

    ansible-playbook -i hosts server_deploy.yml --ask-become-pass --extra-vars "restart=True"


To install dependencies:

    ansible-playbook -i hosts server_deploy.yml --ask-become-pass --extra-vars "install=True restart=True"

To reset the site:

    ansible-playbook -i hosts server_deploy.yml --ask-become-pass --extra-vars "reset=True"

