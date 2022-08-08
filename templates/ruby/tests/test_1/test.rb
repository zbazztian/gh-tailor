#class User < ApplicationRecord
#  def self.authenticate(name, pass)
#    # BAD: possible untrusted input interpolated into SQL fragment
#    find(:first, :conditions => "name='#{name}' and pass='#{pass}'")
#  end
#end
#
#class FooController < ActionController::Base
#  def some_request_handler
#    User.authenticate(params[:name], params[:pass])
#  end
#end
